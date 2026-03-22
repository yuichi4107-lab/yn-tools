# YN Tools - デプロイ手順書

## 1. 事前準備（外部サービス）

### Google OAuth 設定
1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクト作成
2. **APIs & Services > Credentials > OAuth 2.0 Client IDs** を作成
3. **Authorized redirect URIs** に追加:
   - `https://yn-tools.onrender.com/auth/callback`
4. Client ID と Client Secret をメモ

### Stripe 設定
1. [Stripe Dashboard](https://dashboard.stripe.com/) でアカウント作成
2. **本番API キー** を取得（sk_live_xxx, pk_live_xxx）
3. **Products** で月額プランを作成:
   - 名称: YN Tools Pro
   - 金額: ¥500/月（recurring）
   - Price ID をメモ（price_xxx）
4. **Developers > Webhooks** でエンドポイント作成:
   - URL: `https://yn-tools.onrender.com/billing/webhook`
   - イベント: `checkout.session.completed`, `invoice.paid`, `customer.subscription.deleted`
   - Signing secret をメモ（whsec_xxx）

### Google Places API
1. Google Cloud Console で **Places API** を有効化
2. APIキーを作成（制限: HTTP リファラー or IP）

### 暗号化キー生成
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## 2. Render デプロイ

### 方法A: render.yaml (推奨)
1. GitHubリポジトリを作成しpush
2. Render Dashboard > **New > Blueprint** > リポジトリ選択
3. `render.yaml` が自動検出される
4. 環境変数を設定（下記参照）
5. **Apply** でデプロイ開始

### 方法B: 手動
1. Render Dashboard > **New > Web Service** > リポジトリ選択
2. 設定:
   - Runtime: Python
   - Build: `pip install -r requirements.txt && playwright install chromium --with-deps`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. **New > PostgreSQL** でDB作成（Free プラン）
4. 環境変数を設定

### 環境変数一覧

| 変数名 | 値 | 備考 |
|--------|-----|------|
| `APP_ENV` | `production` | |
| `DATABASE_URL` | (自動) | PostgreSQL から自動設定 |
| `SECRET_KEY` | (自動生成) | Render が自動生成 |
| `GOOGLE_CLIENT_ID` | `xxx.apps.googleusercontent.com` | Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | `GOCSPX-xxx` | Google Cloud Console |
| `GOOGLE_REDIRECT_URI` | `https://yn-tools.onrender.com/auth/callback` | デプロイURL に合わせる |
| `STRIPE_SECRET_KEY` | `sk_live_xxx` | Stripe 本番キー |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_xxx` | Stripe 本番キー |
| `STRIPE_WEBHOOK_SECRET` | `whsec_xxx` | Stripe Webhook |
| `STRIPE_PRICE_ID` | `price_xxx` | 月額500円プラン |
| `GOOGLE_PLACES_API_KEY` | `AIza...` | Places API |
| `ENCRYPTION_KEY` | `xxx=` | Fernet キー（上記で生成） |

## 3. デプロイ後チェック

### 自動チェック
- [ ] `/health` が `{"status": "ok", "db": "connected"}` を返す
- [ ] ランディングページ `/` が表示される

### 手動チェック
- [ ] Google OAuth でログインできる
- [ ] ダッシュボードが表示される
- [ ] 各ツールページにアクセスできる
- [ ] GEMS/GPT ライブラリにデータが表示される（自動seed）
- [ ] コミュニティページが表示される
- [ ] Stripe でアップグレードできる（テスト決済）
- [ ] Stripe Webhook が正常動作する

### 管理者設定
初回ログイン後、PostgreSQL で管理者フラグを設定:
```sql
UPDATE users SET is_admin = true WHERE email = 'your@email.com';
```

## 4. ドメイン設定（任意）

1. Render Dashboard > Web Service > Settings > Custom Domains
2. ドメインを追加
3. DNS レコード設定（CNAME: `yn-tools.onrender.com`）
4. Google OAuth と Stripe Webhook の URL を更新

## 5. 運用

### モニタリング
- Render Dashboard > Logs でリアルタイムログ確認
- `/health` エンドポイントで死活監視

### バックアップ
- Render PostgreSQL は自動バックアップあり（有料プラン）
- Free プランは手動バックアップ推奨: `pg_dump`

### スケーリング
- Free プラン: 750h/月（15分アイドルでスリープ）
- Starter プラン ($7/月): 常時起動、カスタムドメインSSL
