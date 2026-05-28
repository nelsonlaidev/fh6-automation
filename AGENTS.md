# AGENTS.md

## Changelog 格式

`CHANGELOG.md` 使用以下結構：

```markdown
## 版本號或 Unreleased

### 新增

### 調整

### 修正

### 破壞性變更
```

規則：

- 每個版本使用 `##` 標題，分類使用 `###` 標題。
- 只列出有內容的分類，不保留空分類。
- 每條項目以 `-` 開頭，一句話描述變更。
- 破壞性變更需說明遷移方式。
- Commit message 使用 conventional commits 格式：`feat:`、`fix:`、`refactor!:`、`docs:`、`chore:`。

## 程式碼風格

- 不使用底線前綴（如 `_start_time`），直接用 `start_time`。
