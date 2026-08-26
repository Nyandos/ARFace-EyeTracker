# ARFace-Eyetracker (FPS Eye-Tracking & Gaze Toolkit)

FaceID（TrueDepth）対応 iPhone を空間アイトラッキングセンサーとして活用し、ローカルUDP経由でPC上のゲーム画面最前面に超低遅延・完全透過で視線ポインターを描画する競技FPS・エイム練習向けアイトラッキングシステムです。

---

## 主な特徴

- **FaceID (TrueDepth) 3D空間トラッキング**: iPhoneの赤外線ドットプロジェクタを活用し、暗所・逆光・画面の照り返しに影響されずに3D頭部姿勢と視線ベクトルを取得。
- **超低負荷・PC最適化**: 画像処理・AI推論はiPhone側で完結。PC側は座標受信と幾何計算のみを行うため、ゲーム中のCPU/GPU負荷は極小。
- **完全透過 & クリック透過 HUD**: Windows Win32 API (`WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE`) によるボーダーレス最前面オーバーレイ。Apex, VALORANT, Overwatch, KovaaK's, Aim Lab等のプレイを一切邪魔しません。
- **適応型 1€ Filter (One-Euro Filter)**: 静止時のジッターを完全に抑えつつ、高速な敵への視線移動（サッカード）には遅延ゼロで追従。
- **ワンタッチ 9点キャリブレーション**: 画面上のターゲットを順番に見つめるだけで、モニターと頭部の相対位置関係を学習し高精度マッピング。
- **iOS 省電力・暗転モード**: 長時間プレイ時の発熱・バッテリー消費・サーマルスロットリングを抑制するブラックアウトモード搭載。
- **PCモックテスター付属**: iPhone実機が手元になくても、PC単体で仮想パケットを送信してHUDやキャリブレーションの動作検証が可能。

---

## システム構成

```
ARFace-Eyetracker/
├── ios/
│   └── ARFaceTrackerApp/      # iOS Swift / ARKit クライアントアプリ
│       ├── ARFaceDataSender.swift
│       ├── ContentView.swift
│       ├── ARFaceTrackerApp.swift
│       └── Info.plist
├── pc/
│   ├── venv/                  # Python 3.11 仮想環境
│   ├── requirements.txt       # 依存ライブラリ (PyQt6, numpy, scipy, screeninfo)
│   ├── main.py                # PC側エントリーポイント (GUI & HUD起動)
│   ├── core/                  # 通信・幾何計算・フィルタ・キャリブレーション
│   ├── ui/                    # コントロールパネル・透過HUD・キャリブレーション画面
│   └── tools/                 # モックテストツール (mock_sender.py)
└── README.md
```

---

## セットアップ手順 (PC側 / Python)

### 1. 仮想環境の有効化

PowerShell または コマンドプロンプトで `ARFace-Eyetracker/pc` フォルダに移動します：

```powershell
cd c:\Users\keita\Desktop\localProjects\ARFace-Eyetracker\pc

# PowerShellの場合:
.\venv\Scripts\Activate.ps1

# コマンドプロンプトの場合:
.\venv\Scripts\activate.bat
```

*(※依存ライブラリは既に venv 内にインストール済みです。必要に応じて `pip install -r requirements.txt`)*

### 2. PC側アプリの起動

```powershell
python main.py
```

- 画面上に **「ARFace-Eyetracker」コントロールパネル** と **透明なHUDオーバーレイ** が起動します。
- コントロールパネル上部に表示されている **「PC 受信先 (例: 192.168.x.x:5005)」** を確認してください。

---

## iOSクライアントの準備 (iPhone)

### 必要環境
- **iPhone**: FaceID (TrueDepth) 搭載端末 (iPhone X 以降。※iPhone SEシリーズは非対応)
- **ネットワーク**: PCとiPhoneが同じWi-Fiルーター（同一ローカルLAN）に接続されていること

---

### 【方法1】Windows環境のみで導入する場合 (Mac不要・推奨)

GitHubの無料クラウドサーバー（macOSランナー）でアプリを自動ビルドし、Windows上の無料ツールでiPhoneに転送します。

1. **GitHubリポジトリの作成 & Push**:
   - GitHubで新規リポジトリを作成し、このプロジェクトをpushします。
   ```powershell
   cd c:\Users\keita\Desktop\localProjects\ARFace-Eyetracker
   git init
   git add .
   git commit -m "Initial commit with Raw Stream & GitHub Actions"
   git branch -M main
   git remote add origin https://github.com/<あなたのユーザー名>/<リポジトリ名>.git
   git push -u origin main
   ```
2. **GitHub ActionsでIPAをダウンロード**:
   - GitHubリポジトリの **「Actions」** タブを開きます。
   - `Build iOS IPA (No Mac Required)` が自動実行されるので、完了（緑のチェック）を待ちます（約2〜3分）。
   - 完了した実行ログ画面の一番下にある **Artifacts** から `ARFaceTrackerApp-iOS.zip` をダウンロードし、解凍して `ARFaceTrackerApp.ipa` を取り出します。
3. **WindowsからiPhoneへインストール (Sideloadly)**:
   - PCに **[Sideloadly](https://sideloadly.io/)** (無料) をインストール。
   - iPhoneをUSBケーブルでPCに接続（iPhone画面で「このコンピュータを信頼」をタップ）。
   - Sideloadlyに `ARFaceTrackerApp.ipa` をドラッグ＆ドロップ。
   - 自分のApple ID（無料アカウントでOK）を入力して **「Start」** をクリック。
   - インストール後、iPhoneの `設定 > 一般 > VPNとデバイス管理` から、自分のApple IDを「信頼」に設定。
4. **アプリ起動 & 送信**:
   - iPhoneで「ARFaceTracker」を起動。
   - PCのIPアドレスとポート（5005）を入力し、プロトコル（**Raw JSON (全生データ)** または **Fast Binary**）を選択。
   - **「START UDP STREAM」** をタップすると、PC側へリアルタイムに生データがストリーミングされます。

---

### 【方法2】Macをお持ちの場合 (Xcode利用)
1. MacのXcodeで `ios/project.yml` を使ってプロジェクトを生成（`brew install xcodegen && xcodegen generate`）、または手動で新規SwiftUIアプリを作成。
2. iPhoneをMacに接続し、実機ビルド＆実行。

---

## 開発・デバッグ用 モックテスト (iPhoneなしで検証)

iPhone実機がない場合でも、付属のシミュレーターで全機能のテストが可能です：

1. 別のターミナルを開き、仮想環境を有効化：
   ```powershell
   cd c:\Users\keita\Desktop\localProjects\ARFace-Eyetracker\pc
   .\venv\Scripts\Activate.ps1
   ```
2. モック送信ツールを実行：
   ```powershell
   python tools/mock_sender.py
   ```
3. コントロールパネルのインジケーターが **「🟢 受信中 (良好 - 60.0 FPS)」** に変わり、画面上で視線ポインターがスムーズに動くことを確認できます。
4. コントロールパネルの **「🎯 キャリブレーション開始 (9点)」** をクリックすると、全画面でターゲットリングが表示され、校正フローがテストできます。

---

## 操作方法 & カスタマイズ

- **キャリブレーション**: 「🎯 キャリブレーション開始 (9点)」を押すと、画面上の9箇所のターゲットを順に見つめるだけで自動学習されます（ESCキーで中断）。
- **スムージング感度**:
  - `⚡ エイム重視 (超低遅延)`: 競技FPS向け。サッカード時の遅延が極小。
  - `⚖️ バランス`: 標準的な視線追従。
  - `🛡️ 安定性重視`: 配信や録画時にポインターの微小な揺れを完全に抑えたい場合。
- **ポインター外観**: ネオンシアン、ライムグリーン、ルビーレッド等のカラー、サイズ（px）、不透明度をリアルタイムに変更可能。
- **HUD非表示**: 「👁️ HUDオーバーレイ」ボタンでいつでも一時非表示にできます。
