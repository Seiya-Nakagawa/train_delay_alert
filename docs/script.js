document.addEventListener('DOMContentLoaded', async () => {
    const routeListContainer = document.getElementById('routeListContainer');
    const addRowButton = document.getElementById('addRowButton');
    const userInfoDiv = document.getElementById('userInfo');
    const userIdSpan = document.getElementById('userId');

    const MAX_ROUTES = 5;
    let lineUserId = null;
    const initialRoutes = ['山手線'];
    let allRoutes = []; // 全路線名データをここに格納

    // --- メインの初期化処理 ---
    async function main() {
        const params = new URLSearchParams(window.location.search);

        // 1. 認可コードをLambdaに連携 (URLにcodeがあれば)
        const authCode = params.get('code');
        if (authCode) {
            sendAuthCodeToLambda(authCode);
        }

        // 2. LINE User IDの処理
        const userId = params.get('userId');
        if (userId) {
            lineUserId = userId;
            userIdSpan.textContent = lineUserId;
            userInfoDiv.style.display = 'block';
        }

        // 3. 路線データの読み込み
        try {
            const response = await fetch('routes.json');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            allRoutes = data;
        } catch (error) {
            console.error('路線データの読み込みに失敗しました:', error);
            alert('路線データの読み込みに失敗したため、オートコンプリート機能は無効になります。');
            // allRoutesは空のままになる
        }

        // 4. 初期路線の表示
        initializeRoutes();

        // 5. イベントリスナーの設定
        setupEventListeners();
    }

    // --- Lambdaへ認可コードを送信する関数（シミュレーション） ---
    function sendAuthCodeToLambda(code) {
        const lambdaEndpoint = config.lambdaEndpoint; // config.jsからURLを取得

        const payload = {
            authorizationCode: code
        };

        console.log('認可コードをLambdaに送信します:');
        console.log(`  -> エンドポイント: ${lambdaEndpoint}`);
        console.log('  -> ペイロード:', payload);

        // 下記は実際のバックエンド連携時に有効化する
        /*
        fetch(lambdaEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Lambdaからの応答:', data);
            // ここで受け取ったユーザーIDなどを処理する
        })
        .catch(error => {
            console.error('Lambdaへのリクエストに失敗しました:', error);
        });
        */
    }

    // --- 路線リストの初期化 ---
    function initializeRoutes() {
        routeListContainer.innerHTML = '';
        const routesToDisplay = initialRoutes.slice(0, MAX_ROUTES);
        routesToDisplay.forEach(route => {
            const routeRow = createRouteRow(route);
            routeListContainer.appendChild(routeRow);
        });
    }

    // --- 路線入力の行を生成する関数 ---
    function createRouteRow(value) {
        const row = document.createElement('div');
        row.classList.add('route-row');
        const wrapper = document.createElement('div');
        wrapper.classList.add('route-input-wrapper');
        const input = document.createElement('input');
        input.type = 'text';
        input.classList.add('route-input');
        input.value = value;
        input.placeholder = '路線名を入力';
        const suggestionsList = document.createElement('div');
        suggestionsList.classList.add('suggestions-list');

        input.addEventListener('input', () => showSuggestions(input, suggestionsList));

        const deleteButton = document.createElement('button');
        deleteButton.textContent = '-';
        deleteButton.classList.add('delete-row-btn');
        deleteButton.addEventListener('click', () => row.remove());

        wrapper.appendChild(input);
        wrapper.appendChild(suggestionsList);
        row.appendChild(wrapper);
        row.appendChild(deleteButton);
        return row;
    }

    // --- 候補を表示する関数 ---
    function showSuggestions(inputElement, suggestionsListElement) {
        const value = inputElement.value.trim();
        suggestionsListElement.innerHTML = '';
        if (value.length === 0 || allRoutes.length === 0) return;

        const suggestions = allRoutes.filter(route => route.includes(value)).slice(0, 10);
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.classList.add('suggestion-item');
            item.textContent = suggestion;
            item.addEventListener('mousedown', () => {
                inputElement.value = suggestion;
                suggestionsListElement.innerHTML = '';
            });
            suggestionsListElement.appendChild(item);
        });
    }

    // --- イベントリスナーをまとめる関数 ---
    function setupEventListeners() {
        const saveButton = document.getElementById('saveButton');

        saveButton.addEventListener('click', () => {
            // 1. User IDのチェック
            if (!lineUserId) {
                alert('LINEユーザーIDが取得できていません。リッチメニューから再度アクセスしてください。');
                return;
            }

            // 2. 登録路線の取得
            const routeInputs = document.querySelectorAll('.route-input');
            const routes = Array.from(routeInputs)
                .map(input => input.value.trim())
                .filter(route => route !== '');

            if (routes.length === 0) {
                alert('保存する路線がありません。');
                return;
            }

            // 3. 送信データの作成
            const payload = {
                userId: lineUserId,
                routes: routes
            };

            // 4. バックエンドへの送信（シミュレーション）
            console.log('以下のデータをバックエンドに送信します:', payload);
            alert(`以下の内容で保存しました：\n\n路線: ${routes.join('、')}`);
        });

        addRowButton.addEventListener('click', () => {
            const currentRows = routeListContainer.getElementsByClassName('route-row').length;
            if (currentRows >= MAX_ROUTES) {
                alert(`登録できる路線は${MAX_ROUTES}つまでです。`);
                return;
            }
            routeListContainer.appendChild(createRouteRow(''));
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.route-input-wrapper')) {
                document.querySelectorAll('.suggestions-list').forEach(list => {
                    list.innerHTML = '';
                });
            }
        });
    }

    // --- 初期化処理を実行 ---
    main();
});