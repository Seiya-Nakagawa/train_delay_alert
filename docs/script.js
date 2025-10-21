// script.js

// DOMContentLoadedイベントで、HTMLの読み込み完了後に処理を開始
document.addEventListener('DOMContentLoaded', async () => {

    // --- HTML要素の取得 ---
    const routeListContainer = document.getElementById('routeListContainer');
    const addRowButton = document.getElementById('addRowButton');
    const saveButton = document.getElementById('saveButton');
    const userInfoDiv = document.getElementById('userInfo');
    const userIdSpan = document.getElementById('userId');
    const messageArea = document.getElementById('messageArea');
    const messageText = document.getElementById('messageText');
    const formContainer = document.getElementById('formContainer');
    const startTimeInput = document.getElementById('startTime');
    const endTimeInput = document.getElementById('endTime');
    const allDayCheckbox = document.getElementById('allDayCheckbox');
    const timeInputs = document.getElementById('timeInputs');
    const dayOfWeekContainer = document.getElementById('dayOfWeekContainer');

    // --- グローバル変数 ---
    const MAX_ROUTES = 5;
    let lineUserId = null; // ログインしたユーザーのIDを保持
    let allRoutes = []; // 全路線名の候補リスト

    /**
     * メイン処理：ページの読み込み時に実行される
     */
    async function main() {
        // 1. 全路線データを非同期で読み込む
        loadAllRoutes(); 

        // 2. URLから認可コードを取得
        const params = new URLSearchParams(window.location.search);
        const authCode = params.get('code');

        if (!authCode) {
            displayMessage('エラー: ログイン情報が見つかりません。LINEのリッチメニューから再度アクセスしてください。', true);
            return;
        }

        // 3. 認可コードをLambdaに送信してユーザー情報を取得
        const userData = await getUserDataFromLambda(authCode);

        // userDataが取得できたか、また必須のlineUserIdが含まれているかを確認
        if (userData && userData.lineUserId) {
            lineUserId = userData.lineUserId;
            
            // 4. ユーザー情報を画面に表示
            // userIdSpan.textContent = lineUserId;
            // userInfoDiv.style.display = 'block';

            // 5. 取得したデータでフォームを初期化
            initializeSettings(userData);
            
            // 6. フォームを表示し、メッセージエリアを非表示にする
            formContainer.style.display = 'block';
            messageArea.style.display = 'none';

        } else {
            // ユーザー情報が取得できなかった、またはレスポンス形式が不正な場合
            console.error('取得したユーザーデータが不正です:', userData);
            displayMessage('エラー: ユーザー情報の取得に失敗しました。時間をおいて再度お試しください。', true);
        }

        // 7. ボタンのイベントリスナーを設定
        setupEventListeners();
    }

    /**
     * Lambdaに認可コードを送信し、ユーザーIDと登録済み路線を取得する
     * @param {string} code - 認可コード
     * @returns {Promise<object|null>} ユーザーデータ or null
     */
    async function getUserDataFromLambda(code) {
        try {
            const response = await fetch(config.lambdaEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ authorizationCode: code })
            });

            if (!response.ok) {
                throw new Error(`Lambdaからの応答エラー: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Lambdaからの応答:', data);
            return data; // 例: { userId: 'U123...', routes: ['山手線'] }

        } catch (error) {
            console.error('Lambdaへのリクエストに失敗しました:', error);
            return null;
        }
    }

    /**
     * routes.jsonから全路線名を読み込み、グローバル変数に格納
     */
    async function loadAllRoutes() {
        try {
            const response = await fetch('routes.json');
            if (!response.ok) throw new Error('路線リストの取得に失敗');
            allRoutes = await response.json();
        } catch (error) {
            console.error('routes.jsonの読み込みエラー:', error);
            // 候補機能が使えなくなるが、アプリの動作は継続させる
        }
    }

    /**
     * ユーザーデータでフォーム全体を初期化する
     * @param {object} userData - ユーザー情報
     */
    function initializeSettings(userData) {
        const { 
            routes = [], 
            notificationStartTime = '07:00', 
            notificationEndTime = '09:00',
            isAllDay = false,
            notificationDays = ['mon', 'tue', 'wed', 'thu', 'fri'] // デフォルトは平日
        } = userData;

        // 時間帯設定
        startTimeInput.value = notificationStartTime;
        endTimeInput.value = notificationEndTime;
        allDayCheckbox.checked = isAllDay;
        timeInputs.style.display = isAllDay ? 'none' : '';

        // 曜日設定
        const dayCheckboxes = dayOfWeekContainer.querySelectorAll('input[type="checkbox"]');
        dayCheckboxes.forEach(checkbox => {
            checkbox.checked = notificationDays.includes(checkbox.value);
        });

        // "毎日"チェックボックスの状態を更新
        const dayEveryCheckbox = document.getElementById('dayEvery');
        const individualDayCheckboxes = Array.from(dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)'));
        dayEveryCheckbox.checked = individualDayCheckboxes.length > 0 && individualDayCheckboxes.every(cb => cb.checked);

        // 路線リストを初期化
        routeListContainer.innerHTML = ''; // コンテナをクリア
        if (routes.length > 0) {
            routes.forEach(route => {
                const routeRow = createRouteRow(route);
                routeListContainer.appendChild(routeRow);
            });
        } else {
            // 登録データがない場合は、空の入力欄を1つ追加
            routeListContainer.appendChild(createRouteRow(''));
        }
    }

    /**
     * 路線入力の行（入力欄、候補リスト、削除ボタン）を生成する
     * @param {string} value - 入力欄の初期値
     * @returns {HTMLElement} 生成された行のDIV要素
     */
    function createRouteRow(value = '') {
        const row = document.createElement('div');
        row.className = 'route-row';

        const wrapper = document.createElement('div');
        wrapper.className = 'route-input-wrapper';

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'route-input';
        input.value = value;
        input.placeholder = '路線名を入力';
        
        const suggestionsList = document.createElement('div');
        suggestionsList.className = 'suggestions-list';

        input.addEventListener('input', () => showSuggestions(input, suggestionsList));
        
        const deleteButton = document.createElement('button');
        deleteButton.textContent = '-';
        deleteButton.className = 'delete-row-btn';
        deleteButton.addEventListener('click', () => row.remove());

        wrapper.appendChild(input);
        wrapper.appendChild(suggestionsList);
        row.appendChild(wrapper);
        row.appendChild(deleteButton);
        return row;
    }
    
    /**
     * 入力内容に基づいて候補リストを表示する
     */
    function showSuggestions(inputElement, suggestionsListElement) {
        const value = inputElement.value.trim();
        suggestionsListElement.innerHTML = '';
        if (value.length === 0 || allRoutes.length === 0) return;

        const suggestions = allRoutes.filter(route => route.line_name.includes(value)).slice(0, 10);
        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion.line_name;
            item.addEventListener('mousedown', () => { // clickではなくmousedownを使うことでblurイベントより先に発火させる
                inputElement.value = suggestion.line_name;
                suggestionsListElement.innerHTML = '';
            });
            suggestionsListElement.appendChild(item);
        });
    }

    /**
     * 保存ボタンや追加ボタンなどのイベントリスナーを設定
     */
    function setupEventListeners() {
        // 全時間帯チェックボックス
        allDayCheckbox.addEventListener('change', () => {
            timeInputs.style.display = allDayCheckbox.checked ? 'none' : '';
        });

        // 曜日チェックボックス
        const dayEveryCheckbox = document.getElementById('dayEvery');
        const individualDayCheckboxes = Array.from(dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)'));

        dayEveryCheckbox.addEventListener('change', () => {
            individualDayCheckboxes.forEach(checkbox => {
                checkbox.checked = dayEveryCheckbox.checked;
            });
        });

        individualDayCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                if (individualDayCheckboxes.every(cb => cb.checked)) {
                    dayEveryCheckbox.checked = true;
                } else {
                    dayEveryCheckbox.checked = false;
                }
            });
        });

        // 保存ボタン
        saveButton.addEventListener('click', async () => {
            // 路線
            const routeInputs = document.querySelectorAll('.route-input');
            const routesToSave = Array.from(routeInputs)
                .map(input => input.value.trim())
                .filter(route => route !== ''); // 空の入力は除外

            // 曜日
            const dayCheckboxes = dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)');
            const selectedDays = Array.from(dayCheckboxes)
                .filter(checkbox => checkbox.checked)
                .map(checkbox => checkbox.value);

            const payload = {
                userId: lineUserId,
                routes: routesToSave,
                notificationStartTime: startTimeInput.value,
                notificationEndTime: endTimeInput.value,
                isAllDay: allDayCheckbox.checked,
                notificationDays: selectedDays
            };
            
            displayMessage('保存中...', false);
            formContainer.style.display = 'none'; // 保存中はフォームを非表示

            try {
                // Lambdaに保存リクエストを送信
                const response = await fetch(config.lambdaEndpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                if (!response.ok) throw new Error('保存に失敗しました');

                displayMessage('保存しました！', false);

            } catch (error) {
                console.error('保存リクエスト失敗:', error);
                displayMessage('エラー: 保存に失敗しました。', true);
            } finally {
                // 成功・失敗に関わらず1.5秒後にフォームを再表示
                setTimeout(() => {
                    messageArea.style.display = 'none';
                    formContainer.style.display = 'block';
                }, 1500);
            }
        });

        // 行追加ボタン
        addRowButton.addEventListener('click', () => {
            if (routeListContainer.childElementCount < MAX_ROUTES) {
                routeListContainer.appendChild(createRouteRow(''));
            } else {
                alert(`登録できる路線は${MAX_ROUTES}つまでです。`);
            }
        });

        // 候補リスト以外の場所をクリックしたら候補を閉じる
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.route-input-wrapper')) {
                document.querySelectorAll('.suggestions-list').forEach(list => list.innerHTML = '');
            }
        });
    }
    
    /**
     * ユーザーへのメッセージを表示する
     * @param {string} text - 表示するメッセージ
     * @param {boolean} isError - エラーメッセージかどうか
     */
    function displayMessage(text, isError) {
        messageArea.style.display = 'block';
        messageText.textContent = text;
        messageText.style.color = isError ? 'red' : 'black';
        if (isError) {
            formContainer.style.display = 'none'; // エラー時はフォームを隠す
        }
    }

    // --- すべての準備が整ったので、メイン処理を実行 ---
    main();
});