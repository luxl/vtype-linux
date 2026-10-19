#include "pinyin_scheme.h"
#include "config.h"
#include <fcitx-config/rawconfig.h>
#include <cstdlib>
#include <iostream>

int main() {
    using namespace fcitx;
    const char *invalid[] = {nullptr, "", "8", "9", "-1", "3x", "03", " 3", "3 "};
    for (const char *value : invalid) {
        if (wetype_double_pin_solution(value) != 0) {
            std::cerr << "错误方案未退回全拼\n";
            return EXIT_FAILURE;
        }
    }
    for (int expected = 0; expected <= 7; ++expected) {
        const char value[] = {static_cast<char>('0' + expected), '\0'};
        if (wetype_double_pin_solution(value) != expected) {
            std::cerr << "官方方案编号解析错误\n";
            return EXIT_FAILURE;
        }
    }
    // 已保存的小鹤配置保持兼容，新增微软配置可往返保存。
    for (const auto &[name, expected] : {
            std::pair{"全拼", 0}, {"小鹤双拼", 3}, {"微软双拼", 2}}) {
        WeTypeConfig config;
        RawConfig raw, saved;
        raw["PinyinScheme"] = name;
        config.load(raw, true);
        config.save(saved);
        if (doublePinSolution(*config.pinyinScheme) != expected ||
            saved["PinyinScheme"].value() != name) {
            std::cerr << "拼音方案配置或官方编号错误\n";
            return EXIT_FAILURE;
        }
    }
    for (const auto &[buffer, expected] : {
            std::pair{"", false}, {"b", true}, {"bz", false}, {"bzj", true},
            {"bzj;", false}, {"j;j", true}, {"ABC", false}, {"bZj", false},
            {";", false}, {"b;;", false}, {"bz'", false}}) {
        if (doublePinSemicolon(PinyinScheme::Microsoft, buffer) != expected ||
            doublePinSemicolon(PinyinScheme::FullPinyin, buffer) ||
            doublePinSemicolon(PinyinScheme::Flypy, buffer)) {
            std::cerr << "分号编码和标点边界错误\n";
            return EXIT_FAILURE;
        }
    }
    return EXIT_SUCCESS;
}
