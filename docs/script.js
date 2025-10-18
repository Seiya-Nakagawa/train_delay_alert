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
        // 1. LINE User IDの処理
        const params = new URLSearchParams(window.location.search);
        const userId = params.get('userId');
        if (userId) {
            lineUserId = userId;
            userIdSpan.textContent = lineUserId;
            userInfoDiv.style.display = 'block';
        }

        // 2. 路線データの読み込み
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

        // 3. 初期路線の表示
        initializeRoutes();

        // 4. イベントリスナーの設定
        setupEventListeners();
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