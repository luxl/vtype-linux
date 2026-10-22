#!/usr/bin/env python3
"""禁用后台 scan_signature 环境完整性与词库反篡改校验补丁。

微信输入法 4.0.1 引擎后台定时触发 scan_signature (0x21c399c)，在 Linux/QEMU 环境下
词库校验失败后走向异常解引用分支，导致定期触发 SIGSEGV (signal 11)。
本补丁在 scan_signature 入口写入 ret (0xd65f03c0)，直接提前返回，根治崩溃。
"""
import hashlib, struct, sys

SO = sys.argv[1] if len(sys.argv) > 1 else 'runtime/libwxhld.so'
SITE = 0x21c399c

# 只接受已核对的 4.0.1 原库及两项补丁的组合，未知构建不写入。
SUPPORTED_SHA256 = {
    "f53f478bc99035e81ca72130735edcada5e6684f202d16927819c0f1131cca83",
    "e8610a81e40f76f0aa27f53121a6ccefd7d8b048f844cbec137601f286c84d28",
    "6bba575e72d49cb152e66b04ed8a9368db637181759295031ee1a45f03c97ba4",
    "c86328992c9311c8eefa9f7313c74c5fa6bff7786a284f826c3da7c267047feb",
}

data = bytearray(open(SO, 'rb').read())
if hashlib.sha256(data).hexdigest() not in SUPPORTED_SHA256:
    raise RuntimeError('引擎校验失败：此补丁只支持已核对的微信输入法 4.0.1')
cur = struct.unpack_from('<I', data, SITE)[0]

# 如果未打补丁，入口指令应为 stp x29, x30, [sp, #-96]! (0xa9ba7bfd)
RET = struct.pack('<I', 0xd65f03c0)
if cur == 0xa9ba7bfd:
    data[SITE:SITE+4] = RET
    open(SO, 'wb').write(data)
    print(f'patched: disabled scan_signature @ {SITE:#x} with ret')
elif cur == 0xd65f03c0:
    print(f'already patched: scan_signature @ {SITE:#x} has ret')
else:
    raise RuntimeError(f'unexpected instruction @ {SITE:#x}: {cur:#x}')
