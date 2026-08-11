import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

const eslintConfig = [
  // 复刻 `next lint` 的默认忽略范围，避免扫描 node_modules / 构建产物
  {
    ignores: [
      "**/node_modules/**",
      ".next/**",
      "out/**",
      "build/**",
      "dist/**",
      "coverage/**",
      "next-env.d.ts",
    ],
  },
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  {
    // 只作用于前端源码；排除配置文件自身（message 示例文本也会被 selector 匹配）
    files: ["src/**"],
    rules: {
      // Next 15 + React 19 新 JSX 转换不再需要显式 React 导入
      "react/react-in-jsx-scope": "off",
      // issue #127：禁止调色板硬编码颜色类名，一律走语义 token（docs/design/visual-spec.md §1.5）
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "Literal[value=/(?:^|\\s)(?:text|bg|border)-(?:red|green|yellow|blue|amber|emerald|orange|purple|indigo|pink|teal|cyan)-\\d+/]",
          message:
            "禁止使用调色板颜色类名（如 text-red-500）。请改用语义 token（text-gain/text-loss/text-success/text-warning/text-destructive 及 -soft/-foreground 变体），见 docs/design/visual-spec.md。",
        },
        {
          selector:
            "TemplateElement[value.cooked=/(?:^|\\s)(?:text|bg|border)-(?:red|green|yellow|blue|amber|emerald|orange|purple|indigo|pink|teal|cyan)-\\d+/]",
          message:
            "禁止使用调色板颜色类名（如 text-red-500）。请改用语义 token（text-gain/text-loss/text-success/text-warning/text-destructive 及 -soft/-foreground 变体），见 docs/design/visual-spec.md。",
        },
      ],
    },
  },
];

export default eslintConfig;
