# 路線遅延通知システム (Train Delay Alert)

## 1. 概要

登録した路線の遅延情報をLINEで受け取れるアプリケーションです。
ユーザーは専用のWebサイトから通知を受けたい路線を登録でき、システムが定期的に遅延情報をチェックして、遅延発生時にLINEで通知します。

## 2. システム構成

詳細は以下のシステム構成図を参照してください。

* `./specs/システム構成図.drawio`

### 主要コンポーネント

* **フロントエンド (GitHub Pages):** ユーザーが路線を設定するための静的Webサイト。
* **バックエンド (AWS Lambda): 環境設定の保存、遅延チェック、LINE通知などのコアロジックを実行。
* **データベース (Amazon DynamoDB):** ユーザーのLINE IDと登録路線を紐付けて管理。
* **インフラ管理 (Terraform):** AWSリソースをコードで管理。

## 3. 主な利用技術

* **クラウド:** AWS
* **IaC:** Terraform
* **バックエンド:** Python (AWS Lambda)
* **フロントエンド:** HTML, CSS, JavaScript (GitHub Pages)
* **データベース:** Amazon DynamoDB
* **API:**
  * LINE Messaging API
  * 公共交通オープンデータセンター API

## 4. ディレクトリ構成

```text
.
├── docs/              # GitHub Pagesでホスティングされるフロントエンドのソースコード
├── specs/             # 基本設計書などのドキュメント類
├── terraform/         # AWSリソースを定義するTerraformコード
│   ├── lambda/        # Lambda関数のPythonソースコード
│   └── lambda-layers/ # Lambdaレイヤー（共通ライブラリ）のソース
├── .gitignore
├── pyproject.toml
└── README.md
```

## 5. デプロイ手順

### 前提条件

* AWSアカウント
* Terraform CLI
* LINE Developersアカウント
  * LINEログインチャネル
  * Messaging APIチャネル
* 公共交通オープンデータセンターのアクセストークン

### 手順

1. **リポジトリのクローン**

    ```bash
    git clone https://github.com/your-username/train_delay_alert.git
    cd train_delay_alert
    ```

2. **機密情報の設定**

    以下の情報をAWS Systems Manager パラメータストアに事前に登録します。

    * LINEログインチャネルのチャネルシークレット
    * Messaging APIチャネルのチャネルアクセストークン
    * 公共交通オープンデータセンターのアクセストークン

3. **Terraform変数の設定**

    `terraform`ディレクトリに`terraform.tfvars`ファイルを作成し、環境に合わせて変数を設定します。

    **`terraform/terraform.tfvars` (例)**

    ```hcl
    aws_region                = "ap-northeast-1"
    system_name               = "train-delay-alert"
    env                       = "dev"
    notification_emails       = ["admin@example.com"]
    frontend_redirect_url     = "https://your-github-username.github.io/train_delay_alert/index.html" # ご自身のGitHub PagesのURL
    frontend_origin           = "https://your-github-username.github.io" # ご自身のGitHub Pagesのオリジン
    line_login_channel_id     = "YOUR_LINE_LOGIN_CHANNEL_ID"
    line_post_channel_id      = "YOUR_LINE_MESSAGING_API_CHANNEL_ID"
    # パラメータストアに登録した名前
    line_channel_secret_param_name      = "/train-delay-alert/dev/line_channel_secret"
    line_channel_access_token_param_name = "/train-delay-alert/dev/line_channel_access_token"
    odpt_access_token_param_name        = "/train-delay-alert/dev/odpt_access_token"
    ```

4. **Lambdaレイヤーの作成**

    `requests`ライブラリを含むLambdaレイヤーを作成します。

    ```bash
    cd terraform/lambda-layers
    pip install -r requirements.txt -t ./python
    zip -r python_libraries.zip ./
    cd ../..
    ```

5. **Terraformによるデプロイ**

    ```bash
    cd terraform
    terraform init
    terraform apply
    ```

6. **フロントエンドの設定**

    デプロイ完了後、Terraformの出力に表示される`user_settings_lambda_url`の値を、`docs/config.js`に設定します。

    **`docs/config.js`**

    ```javascript
    const config = {
        API_ENDPOINT: 'https://xxxxxxxxxx.lambda-url.ap-northeast-1.on.aws/' // Terraformの出力結果に書き換える
    };
    ```

7. **GitHub Pagesの有効化**

    GitHubリポジトリの `Settings` > `Pages` で、`docs`ディレクトリをソースとしてGitHub Pagesを有効化します。

## 6. 使い方

1. LINE公式アカウントを友だち追加します。
2. リッチメニューから「路線設定」をタップして、設定画面（GitHub Pages）を開きます。
3. LINEログインを行い、アプリ連携を許可します。
4. 通知を受けたい路線を選択し、「保存」ボタンを押します。
5. 登録した路線で遅延が発生すると、LINEメッセージが届きます。

## 7. 注意事項

* 本システムは公共交通オープンデータセンターが提供する情報を基にしています。情報の正確性やリアルタイム性については、各交通事業者の公式情報も併せてご確認ください。
* APIキーやチャネルシークレットなどの機密情報は、絶対にリポジリにコミットしないでください。
