import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

// issue #127：禁止调色板硬编码颜色类名，一律走语义 token（docs/design/visual-spec.md §1.5）
// 全部源码适用（含豁免文件）。
const paletteColorSelectors = [
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
];

// 2026-08-29：禁止任意值类名（visual-spec §1.5 第 2 道）。
// 范围：text-[…]（§5 四档之外）、p/px/py/pt/pb/pl/pr-[…]、gap/gap-x/gap-y-[…]、rounded-[…]（§7 派生档之外）。
// m 系 / space 系 / w·h 系任意值暂不拦截（多为视口比例或一次性尺寸，见 §1.5）。
const arbitraryValueSelectors = [
  {
    selector:
      "Literal[value=/(?:^|\\s)(?:text|p|px|py|pt|pb|pl|pr|gap|gap-x|gap-y|rounded)-\\[/]",
    message:
      "禁止使用任意值类名（text-[Npx]/p-[Npx]/gap-[Npx]/rounded-[Npx]）。字号走四级档位、间距圆角走派生档，见 docs/design/visual-spec.md §5/§7。",
  },
  {
    selector:
      "TemplateElement[value.cooked=/(?:^|\\s)(?:text|p|px|py|pt|pb|pl|pr|gap|gap-x|gap-y|rounded)-\\[/]",
    message:
      "禁止使用任意值类名（text-[Npx]/p-[Npx]/gap-[Npx]/rounded-[Npx]）。字号走四级档位、间距圆角走派生档，见 docs/design/visual-spec.md §5/§7。",
  },
];

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
      "no-restricted-syntax": [
        "error",
        ...paletteColorSelectors,
        ...arbitraryValueSelectors,
      ],
    },
  },
  // 任意值护栏豁免（visual-spec §1.5 登记；豁免文件仍受调色板拦截）。
  // 永久：shadcn 基件 vendor 源码，保持与上游同步。
  {
    files: ["src/components/ui/**"],
    rules: {
      "no-restricted-syntax": ["error", ...paletteColorSelectors],
    },
  },
  // 临时（ratchet，只减不增）：存量 text-[Npx] 13 处，改动页面顺手收敛后从此清单移出。
  {
    files: [
      "src/app/portfolio/\\[code\\]/page.tsx",
      "src/components/shared/PositionSections.tsx",
      "src/components/layout/NotificationBell.tsx",
    ],
    rules: {
      "no-restricted-syntax": ["error", ...paletteColorSelectors],
    },
  },
];

export default eslintConfig;
