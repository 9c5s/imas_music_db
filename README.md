# アイマス楽曲データベース

Googleスプレッドシートからアイマス楽曲データベースをJSONファイルとして自動生成・配信するシステムです。

## 配信URL

https://raw.githubusercontent.com/9c5s/imas_music_db/data/imas_music_db.json

## 開発者向け情報

### 自動コード品質チェック

プルリクエスト作成時に、GitHub Actionsによって自動的にコード品質チェックが実行されます。

#### Pythonコード
- **Ruffリンティング**: コードの潜在的な問題を検出
- **Ruffフォーマット**: コードスタイルの一貫性をチェック

#### YAMLファイル
- **yamllint**: YAML構文とスタイルをチェック
- **yamlfix**: YAMLフォーマットの自動修正（ローカル用）

#### その他の機能
- **PRコメント**: 詳細なチェック結果をPRに自動投稿
- **修正方法の提示**: エラー修正のためのコマンドを表示

詳細な開発情報は[CLAUDE.md](./CLAUDE.md)を参照してください。
