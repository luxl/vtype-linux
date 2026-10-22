# Arch Linux / EndeavourOS 本地包

在 x86_64 上用 `PKGBUILD` 构建 `vtype-linux`，通过 pacman 安装、升级和卸载。
Fcitx5、QEMU、Python、OpenSSL、Snappy 使用 Arch 软件包；构建工具使用 AUR 的
`android-ndk-27`，不需要 AppImage 或 appimagetool。

## 构建与安装

在仓库根目录执行：

```sh
bash packaging/arch/build-install.sh
```

依赖统一维护在 `PKGBUILD`：`depends` 是运行依赖，`makedepends` 是编译依赖，
`checkdepends` 用于检查，`optdepends` 列出可选功能依赖。脚本读取当前配方，
用 `pacman -T` 找出缺失项，再交给 `yay` 解析官方仓库和 AUR 依赖（例如 NDK）；
没有 `yay` 时只能安装官方仓库依赖。可选功能依赖不会自动安装。

脚本随后用 `makepkg` 编译并运行检查，成功后用 `pacman -U` 安装。
安装依赖和 VType 时优先弹出 Polkit 认证；没有 `pkexec` 时使用
`sudo`。构建失败会停止，不会继续安装旧包。脚本不会自动重启输入法。

下载缓存保存在 `.deps/arch/sources/`，构建目录在 `.deps/arch/build/`，安装包在
`.deps/arch/packages/`；再次运行会复用下载文件，并重新创建源码构建目录。
只生成安装包可加 `--build-only`；仅替换图标时可加 `--skip-checks` 跳过检查。
也可以进入本目录手动执行 `makepkg -si`。

构建会下载固定提交的源码、Google 的 Android 9
ARM64 运行时镜像和腾讯官方微信输入法 3.5.4 APK。后两项分别约 407 MB、214 MB，
下载后校验固定 SHA256；已有 makepkg 源码缓存会复用。NDK 已安装时直接使用
`/opt/android-ndk`。

本地包在固定源码上应用本目录的 `microsoft-double-pinyin.patch`，加入微软双拼
设置、分号韵母和相应测试；`tray-icon.patch` 让微信拼音使用包内的官方圆形图标。
补丁与下载文件一样校验 SHA256。`0.1.8-5` 已合入上游行内编辑、候选框定位和
Python 启动器改进，微软双拼的分号在行内编辑时按当前光标位置判断。
`0.1.8-6` 通过 `mode-hint.patch` 补上 Shift 中英切换时的光标提示；
Fcitx5 开启紧凑显示时只显示“中”或“英”。

构建过程会运行插件单元测试、离线 Python 测试和真实引擎自检。生成的
`vtype-linux-*.pkg.tar.zst` 包含插件、运行时、官方引擎和预置词库，可在本机用
`sudo pacman -U 包文件` 重新安装。此目录提供本地打包配方，尚未发布到 AUR。

## 启用与自检

```sh
wetype-check --idle-seconds 85
```

自检使用临时个人词库，验证候选、选词、学习和重启。准备好后重启 Fcitx5，在
`fcitx5-configtool` 中添加“微信拼音”，在文本框输入 `nihao`。KDE/Wayland 用户
继续通过系统设置中的虚拟键盘启动 Fcitx5。

包安装不会修改 Fcitx5 分组、重启输入法、关联账号或启用云功能。
升级后重启 Fcitx5，在“微信拼音”的“拼音方案”中选择“微软双拼”。
输入 `nihk` 出“你好”，`bzj;` 出“北京”；Rime 的方案和词库不受影响。
切换到微信拼音时，托盘自动显示官方绿色圆形图标。自定义外观可替换本目录的
`tray-icon.png`（透明背景 PNG），更新 `PKGBUILD` 中对应的 SHA256，再重新打包。
图标随包安装，不需要修改桌面主题。当前 PNG 原图为 152×152，来源于
[微信输入法官网](https://cdn.weread.qq.com/web/wetype/favicon/icon-152.png)，相关权利归腾讯所有。

| 路径或命令 | 用途 |
|---|---|
| `/usr/lib/fcitx5/libfcitx5-wetype.so` | Fcitx5 插件 |
| `/usr/lib/wetype-ime/arm64` | 引擎、预置词库、Android 运行时 |
| `wetype-check` | 使用临时词库自检 |
| `wetype-demo nihao` | 使用日常个人词库查看候选 |
| `wetype-cloud status` | 查看关联与云功能状态 |

个人词库仍在 `~/.local/share/wetype-ime`，设备身份仍在
`~/.local/state/wetype-ime/account`。这些用户数据不属于系统包。

## 从 AppImage 用户安装迁移

先退出 Fcitx5，再备份并移走旧的 `~/.local/lib/wetype-ime/arm64`、
`~/.local/lib/fcitx5/libfcitx5-wetype.so`，以及
`~/.local/share/fcitx5/addon/wetype.conf` 和
`~/.local/share/fcitx5/inputmethod/wetype-im.conf`。
用户目录中的运行时和注册文件优先于系统包，保留它们会继续使用旧版本。
旧的 `~/.local/bin/wetype-ime-engine` 与 `~/.local/bin/wetype-demo` 也应备份移走。

安装本地包后运行 `wetype-check`，再启动 Fcitx5。保留
`~/.local/share/wetype-ime` 和 `~/.local/state/wetype-ime` 中的个人数据。

## 可选云功能

需要时使用 `wetype-cloud`，它会自动选用系统包的运行目录。关联设备、云功能和
剪贴板互通的步骤见仓库的 `docs/安装与使用.md`；其中的
`python3 ~/.local/lib/wetype-ime/arm64/wetype-cloud.py` 可换成 `wetype-cloud`。
云客户端 wxc 另行安装，云功能与剪贴板同步默认关闭。

## 更新与卸载

更新源码版本时，一起更新 `PKGBUILD` 的 `_commit` 和 `pkgver`；修改打包方式时
递增 `pkgrel`。补丁以 `_commit` 指定的上游提交为基线；更新时需适配补丁并更新
对应校验值。已包含微软双拼和图标改动的本地合并提交不能再重复应用这些补丁。
APK 版本、下载地址和校验值必须与该提交的 `scripts/fetch_apk.py` 一致。
修改本地配方后重新生成 `.SRCINFO`：

```sh
makepkg --printsrcinfo > .SRCINFO
bash build-install.sh
```

脚本使用当前 `PKGBUILD` 的固定源码提交，不会自动合并远程代码或更新补丁。

卸载前先退出 Fcitx5，使用 `sudo pacman -R vtype-linux` 移除系统包。
个人词库、设备身份和输入法设置会保留。
