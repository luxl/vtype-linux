#!/usr/bin/env bash
# 按当前 PKGBUILD 编译并安装，下载和构建缓存保存在仓库 .deps/arch 下。
set -euo pipefail

usage() {
  cat <<'EOF'
用法：bash packaging/arch/build-install.sh [选项]

默认编译、运行检查并通过 pacman 安装；优先使用 Polkit 认证。
  --build-only   只生成 VType 安装包
  --skip-checks  跳过 PKGBUILD 的 check()，适合只替换图标时使用
  --noconfirm    跳过 pacman 的安装确认，仍需管理员认证
  -h, --help     显示帮助

依赖从 PKGBUILD 读取；有 yay 时自动解析官方仓库和 AUR 依赖。
脚本直接构建当前仓库源码，包含尚未提交的修改；不会自动拉取或合并远程代码。
EOF
}

build_only=false
skip_checks=false
pacman_options=()
for option in "$@"; do
  case "$option" in
    --build-only) build_only=true ;;
    --skip-checks) skip_checks=true ;;
    --noconfirm) pacman_options+=(--noconfirm) ;;
    -h|--help) usage; exit 0 ;;
    *) printf '不支持的选项：%s\n' "$option" >&2; usage >&2; exit 2 ;;
  esac
done

if (( EUID == 0 )); then
  printf '请以普通用户运行；脚本会在安装软件包时请求管理员认证。\n' >&2
  exit 1
fi
for command in makepkg pacman; do
  command -v "$command" >/dev/null || { printf '缺少命令：%s\n' "$command" >&2; exit 1; }
done
recipe_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd -- "$recipe_dir/../.." && pwd)"
export SRCDEST="${SRCDEST:-$repo_root/.deps/arch/sources}"
export PKGDEST="${PKGDEST:-$repo_root/.deps/arch/packages}"
export BUILDDIR="${BUILDDIR:-$repo_root/.deps/arch/build}"
mkdir -p -- "$SRCDEST" "$PKGDEST" "$BUILDDIR"

if command -v pkexec >/dev/null; then
  auth="$(command -v pkexec)"
elif command -v sudo >/dev/null; then
  auth="$(command -v sudo)"
else
  printf '需要 pkexec 或 sudo 来安装依赖和软件包。\n' >&2
  exit 1
fi
pacman_path="$(command -v pacman)"

# 复用 makepkg 自己的配置加载函数，保留系统及用户设置，只调整认证方式。
makepkg_config="$(mktemp "$BUILDDIR/vtype-makepkg.XXXXXX.conf")"
trap 'rm -f -- "$makepkg_config"' EXIT
printf 'source_makepkg_config %q\nPACMAN_AUTH=(%q)\n' \
  "${MAKEPKG_CONF:-/etc/makepkg.conf}" "$auth" > "$makepkg_config"

cd -- "$recipe_dir"

# 依赖只在 PKGBUILD 中维护；读取当前配方，保留版本约束，不安装可选依赖。
metadata="$(makepkg --config "$makepkg_config" --printsrcinfo)"
mapfile -t dependencies < <(
  awk -F ' = ' -v architecture="$(uname -m)" -v skip="$skip_checks" '
    {
      key = $1
      sub(/^[[:space:]]+/, "", key)
      sub("_" architecture "$", "", key)
      if (key == "depends" || key == "makedepends" ||
          (key == "checkdepends" && skip != "true")) {
        if (!seen[$2]++) print $2
      }
    }
  ' <<< "$metadata"
)
if (( ${#dependencies[@]} )); then
  if missing="$(pacman -T "${dependencies[@]}")"; then
    missing=''
  else
    result=$?
    # pacman -T 用 127 表示存在尚未满足的依赖。
    if (( result != 127 )); then exit "$result"; fi
  fi
  if [[ -n "$missing" ]]; then
    mapfile -t missing_dependencies <<< "$missing"
    if command -v yay >/dev/null; then
      yay -S --needed --asdeps --noremovemake --sudo "$auth" --sudoflags '' \
        "${pacman_options[@]}" "${missing_dependencies[@]}"
    else
      printf '未找到 yay，将从官方仓库安装依赖；AUR 依赖需要先安装 yay。\n'
      "$auth" "$pacman_path" -S --needed --asdeps \
        "${pacman_options[@]}" "${missing_dependencies[@]}"
    fi
  fi
fi

# 先冻结当前源码；makepkg 使用这份归档，不读取另一个上游提交。
export VTYPE_SOURCE_SHA256
VTYPE_SOURCE_SHA256="$(python3 "$repo_root/scripts/export_source.py" \
  --output "$SRCDEST/vtype-linux-source.tar")"
printf '当前源码快照 SHA256：%s\n' "$VTYPE_SOURCE_SHA256"

build_options=(--config "$makepkg_config" --cleanbuild --force --syncdeps)
if "$skip_checks"; then build_options+=(--nocheck); fi
printf '开始构建；安装包目录：%s\n' "$PKGDEST"
makepkg "${build_options[@]}" "${pacman_options[@]}"

# 构建失败会直接退出；只安装这次配方生成的包，不使用目录通配符。
package_list="$(makepkg --config "$makepkg_config" --packagelist)"
mapfile -t package_paths <<< "$package_list"
for package in "${package_paths[@]}"; do
  [[ -f "$package" ]] || { printf '未找到构建产物：%s\n' "$package" >&2; exit 1; }
done
printf '构建完成：\n'
printf '  %s\n' "${package_paths[@]}"
if "$build_only"; then exit 0; fi

"$auth" "$pacman_path" -U "${pacman_options[@]}" "${package_paths[@]}"
pacman -Q vtype-linux
printf '安装完成。准备好后重启 Fcitx5 加载新版插件。\n'
