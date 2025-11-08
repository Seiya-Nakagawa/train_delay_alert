# 路線遅延通知システム (Train Delay Alert)

## 1. 概要

登録した路線の遅延情報をLINEで受け取れるアプリケーションです。
ユーザーは専用のWebサイトから通知を受けたい路線を登録でき、システムが定期的に遅延情報をチェックして、遅延発生時にLINEで通知します。

## 2. システム構成

詳細は以下のシステム構成図を参照してください。

* `./specs/システム構成図.drawio`

### 主要コンポーネント

* **フロントエンド (GitHub Pages):** ユーザーが路線を設定するための静的Webサイト。
* **バックエンド (AWS Lambda)**: 環境設定の保存、遅延チェック、LINE通知などのコアロジックを実行。
* **データベース (Amazon DynamoDB):** ユーザーのLINE IDと登録路線を紐付けて管理。
* **インフラ管理 (Terraform):** AWSリソースをコードで管理。

## 3. 主な利用技術

* **クラウド:** AWS
* **IaC:** Terraform Cloud
* **CI/CD:**GitHub Actions(Lambda)
* **バックエンド:** Python (AWS Lambda)
* **フロントエンド:** HTML, CSS, JavaScript (GitHub Pages)
* **データベース:** Amazon DynamoDB
* **API:**
  * LINE Messaging API
  * 公共交通オープンデータセンター API

## 4. ディレクトリ構成

```text
.
├── .github/
│   └── workflows/     # CI/CDのワークフロー定義
├── docs/              # GitHub Pagesでホスティングされるフロントエンドのソースコード
├── python/            # Lambda関数のPythonソースコード
├── specs/             # 基本設計書などのドキュメント類
├── terraform/         # AWSリソースを定義するTerraformコード
├── .gitignore
├── pyproject.toml
└── README.md
```

## 5. デプロイ

本システムは、インフラ層とアプリケーション層で分離されたCI/CDパイプラインによってデプロイが自動化されています。

* **インフラ (AWSリソース):** Terraform CloudによるVCS-driven workflow

* **アプリケーション (Lambda関数,Lambdaレイヤー):** GitHub Actionsによるデプロイ

### 5.1. インフラのデプロイ (Terraform Cloud)

`terraform`ディレクトリ配下のAWSリソースは、Terraform Cloudによって管理されます。

`main`ブランチに対するプルリクエスト (PR) が作成されると、Terraform Cloudは自動的に`terraform plan`を実行し、変更内容をレビューできます。PRが`main`ブランチにマージされると、自動的に`terraform apply`が実行され、インフラの変更が適用されます。

#### 前提条件

* AWSアカウントとTerraform Cloudアカウントの連携設定

* Terraform CloudのWorkspace作成と、対象リポジトリとの連携設定

* LINE Developersアカウント

* 公共交通オープンデータセンターのアクセストークン

#### 初回セットアップ

1. **機密情報の設定**

    * **Terraform Cloud:**

        Workspaceの`Variables`に、AWS認証情報や以下の変数を環境変数として設定します。機密情報は"Sensitive"に設定してください。

        * `TF_VAR_line_channel_secret_param_name`

        * `TF_VAR_line_channel_access_token_param_name`

        * `TF_VAR_odpt_access_token_param_name`

        * その他`variables.tf`で定義されている変数

    * **AWS Systems Manager パラメータストア:**

        Terraformで参照する以下の機密情報を事前に登録します。

        * LINEログインチャネルのチャネルシークレット

        * Messaging APIチャネルのチャネルアクセストークン

        * 公共交通オープンデータセンターのアクセストークン

    * **GitHub Actions Secrets:**

        GitHubリポジトリの `Settings` > `Secrets and variables` > `Actions` で、AWSへのOIDC接続に使用するIAMロールのARNを `AWS_IAM_ROLE_ARN` という名前で登録します。

2. **インフラのプロビジョニング**

    `terraform`ディレクトリ配下のコードを`main`ブランチにプッシュします。これによりTerraform Cloudがトリガーされ、インフラが構築されます。

3. **フロントエンドの設定**

    Terraform Cloudの実行結果から`user_settings_lambda_url`の値を取得し、`docs/config.js`に設定します。

    **`docs/config.js`**

    ```javascript

    const config = {

        API_ENDPOINT: 'https://xxxxxxxxxx.lambda-url.ap-northeast-1.on.aws/' // Terraformの出力結果に書き換える

    };

    ```

4. **GitHub Pagesの有効化**

    GitHubリポジトリの `Settings` > `Pages` で、`docs`ディレクトリをソースとしてGitHub Pagesを有効化します。

### 5.2. アプリケーションのデプロイ (GitHub Actions)

Lambda関数のソースコードや依存ライブラリは、GitHub Actionsによって自動でデプロイされます。

`python`ディレクトリ配下のソースコード等を変更し`main`ブランチにプッシュすると、対応するワークフローが実行されます。

| ワークフロー | トリガーとなる変更 | 説明 |

| :--- | :--- | :--- |

| **Deploy Lambda Layer** | `python/requirements.txt` | Pythonの依存ライブラリをまとめたLambdaレイヤーをビルドし、AWSにデプロイします。 |

| **Deploy user_settings_lambda** | `python/user_settings_lambda/**` | ユーザー設定用Lambda関数をパッケージ化し、AWSにデプロイします。 |

| **Deploy check_delay_handler** | `python/check_delay_handler/**` | 遅延チェック用Lambda関数をパッケージ化し、AWSにデプロイします。 |

## 6. 使い方

1. LINE公式アカウントを友だち追加します。
2. リッチメニューから「路線設定」をタップして、設定画面（GitHub Pages）を開きます。
3. LINEログインを行い、アプリ連携を許可します。
4. 通知を受けたい路線を選択し、「保存」ボタンを押します。
5. 登録した路線で遅延が発生すると、LINEメッセージが届きます。

## 7. 注意事項

* 本システムは公共交通オープンデータセンターが提供する情報を基にしています。情報の正確性やリアルタイム性については、各交通事業者の公式情報も併せてご確認ください。
* APIキーやチャネルシークレットなどの機密情報は、絶対にリポジリにコミットしないでください。
