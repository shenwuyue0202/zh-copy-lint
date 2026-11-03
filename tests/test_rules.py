import unittest

from zh_copy_lint import fix_text, lint_text


def rules_of(text, **kwargs):
    return [issue.rule for issue in lint_text(text, **kwargs)]


class RuleTests(unittest.TestCase):
    def test_space_between_cjk_and_digits_is_opt_in(self):
        self.assertEqual(rules_of("平均 117 帧。"), [])
        self.assertIn("C001", rules_of("平均 117 帧。", cjk_space="none"))

    def test_no_space_between_cjk_and_digits(self):
        self.assertEqual(rules_of("平均117帧。", cjk_space="none"), [])

    def test_space_between_cjk_chars(self):
        self.assertIn("C002", rules_of("手 机 发 热。"))

    def test_half_width_comma_in_chinese(self):
        self.assertIn("C003", rules_of("这台机器很强,但是太重。"))

    def test_decimal_number_is_not_punctuation(self):
        self.assertNotIn("C003", rules_of("厚度只有3.5mm。"))

    def test_ellipsis(self):
        self.assertIn("C004", rules_of("等等...我再想想。"))

    def test_em_dash(self):
        self.assertIn("C005", rules_of("它不是更快--而是更稳。"))

    def test_repeated_punctuation(self):
        self.assertIn("C006", rules_of("真的？？没开玩笑。"))

    def test_half_width_parentheses_with_cjk(self):
        self.assertIn("C007", rules_of("处理器(酷睿Ultra5)很强。"))

    def test_number_unit_space(self):
        self.assertIn("C008", rules_of("温度74 ℃。"))

    def test_missing_terminal_punctuation(self):
        self.assertIn("C009", rules_of("这是一句没有句号的正文大概有二十来个字"))

    def test_heading_may_skip_period(self):
        self.assertNotIn("C009", rules_of("## 这是一个很长很长很长的小标题"))

    def test_list_item_may_skip_period(self):
        self.assertNotIn("C009", rules_of("- 这是一个列表项而不是正文段落"))

    def test_inline_code_is_skipped(self):
        self.assertEqual(rules_of("设置 `--fix 参数` 之后。"), [])

    def test_fenced_code_block_is_skipped(self):
        text = "```\n平均 117 帧,真的...\n```\n"
        self.assertEqual(rules_of(text), [])

    def test_url_is_skipped(self):
        self.assertEqual(rules_of("参考 https://example.com/a...b 即可。"), [])

    def test_ignore_list(self):
        self.assertEqual(lint_text("平均 117 帧。", ignore=["C001"]), [])


class FixTests(unittest.TestCase):
    def test_fix_all_autofixable_rules(self):
        source = "平均 117 帧,温度 74 ℃...真的？？"
        fixed = fix_text(source, cjk_space="none")
        self.assertEqual(fixed, "平均117帧，温度74℃……真的？")

    def test_fix_keeps_cjk_latin_spaces_by_default(self):
        self.assertEqual(fix_text("平均 117 帧。"), "平均 117 帧。")

    def test_fix_keeps_code(self):
        source = "运行 `npm run  build` 之后。"
        self.assertEqual(fix_text(source), source)

    def test_fix_is_idempotent(self):
        source = "这台手机(不是平板)很轻,只有 480 g。"
        once = fix_text(source)
        self.assertEqual(fix_text(once), once)


if __name__ == "__main__":
    unittest.main()
