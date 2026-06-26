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
    rules: {
      // Next 15 + React 19 新 JSX 转换不再需要显式 React 导入
      "react/react-in-jsx-scope": "off",
    },
  },
];

export default eslintConfig;
