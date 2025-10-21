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
    function createRouteRow(routeData = { line_name: '', line_cd: '' }) {
        const row = document.createElement('div');
        row.className = 'route-row';

        const wrapper = document.createElement('div');
        wrapper.className = 'route-input-wrapper'; // This wrapper will now contain the autocomplete-wrapper and error message

        const autocompleteWrapper = document.createElement('div');
        autocompleteWrapper.className = 'autocomplete-wrapper';

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'route-input';
        input.placeholder = '路線名を入力';
        
        // 渡されたデータで入力欄を初期化
        const routeName = typeof routeData === 'string' ? routeData : routeData.line_name;
        const routeCode = typeof routeData === 'string' ? '' : routeData.line_cd;
        input.value = routeName;
        if (routeCode) {
            input.dataset.lineCd = routeCode;
        }

        const suggestionsList = document.createElement('div');
        suggestionsList.className = 'suggestions-list';
        suggestionsList.style.display = 'none'; // Initially hidden

        const dropdownButton = document.createElement('button');
        dropdownButton.className = 'dropdown-button';
        dropdownButton.innerHTML = '&#9660;'; // Down arrow character

        dropdownButton.addEventListener('click', (e) => {
            e.preventDefault(); // Prevent form submission
            if (suggestionsList.style.display === 'none') {
                showSuggestions(input, suggestionsList, true); // Pass true to force show all
            } else {
                suggestionsList.style.display = 'none';
            }
        });

        input.addEventListener('focus', () => {
            if (input.value.trim() === '') {
                showSuggestions(input, suggestionsList, true); // Show all on focus if empty
            }
        });

        input.addEventListener('blur', (e) => {
            // Delay hiding to allow click on suggestion item
            setTimeout(() => {
                if (!suggestionsList.contains(document.activeElement)) { // Only hide if focus is not on suggestion list
                    suggestionsList.style.display = 'none';
                }
            }, 100);
            validateRouteInput(input);
        });

        const errorMessageElement = document.createElement('div'); // エラーメッセージ要素を追加
        errorMessageElement.className = 'route-error-message';
        errorMessageElement.textContent = '無効な路線名です。候補から選択してください。';

        input.addEventListener('input', () => {
            delete input.dataset.lineCd; // 手入力時にline_cdをクリア
            showSuggestions(input, suggestionsList);
            // ユーザーが入力し始めたらエラー表示を消す
            input.classList.remove('invalid');
            row.classList.remove('has-error');
        });
        
        const deleteButton = document.createElement('button');
        deleteButton.textContent = '-';
        deleteButton.className = 'delete-row-btn';
        deleteButton.addEventListener('click', () => row.remove());

        autocompleteWrapper.appendChild(input);
        autocompleteWrapper.appendChild(dropdownButton);
        autocompleteWrapper.appendChild(suggestionsList); // Suggestions list is now inside autocompleteWrapper

        wrapper.appendChild(autocompleteWrapper);
        wrapper.appendChild(errorMessageElement); // Error message is still directly in route-input-wrapper
        row.appendChild(wrapper);
        row.appendChild(deleteButton);
        return row;
    }
    
    /**
     * 入力内容に基づいて候補リストを表示する
     */
    function showSuggestions(inputElement, suggestionsListElement, forceShow = false) {
        const value = inputElement.value.trim();
        suggestionsListElement.innerHTML = '';

        let suggestions = [];
        if (value.length === 0 && forceShow) {
            suggestions = allRoutes.slice(0, 20); // Show top 20 if empty and forced
        } else if (value.length > 0) {
            suggestions = allRoutes.filter(route => route.line_name.includes(value)).slice(0, 10);
        } else {
            suggestionsListElement.style.display = 'none';
            return;
        }

        if (suggestions.length === 0) {
            suggestionsListElement.style.display = 'none';
            return;
        }

        suggestions.forEach(suggestion => {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.textContent = suggestion.line_name;
            item.addEventListener('mousedown', () => {
                inputElement.value = suggestion.line_name;
                inputElement.dataset.lineCd = suggestion.line_cd;
                suggestionsListElement.style.display = 'none'; // Hide after selection
            });
            suggestionsListElement.appendChild(item);
        });
        suggestionsListElement.style.display = 'block'; // Show the list
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
            const routeInputs = document.querySelectorAll('.route-input');

            // --- バリデーション ---
            let hasValidationErrors = false;
            routeInputs.forEach(input => {
                // 空の入力はバリデーションしない（保存時にfilterで除外されるため）
                if (input.value.trim() !== '') {
                    const isValid = validateRouteInput(input);
                    if (!isValid) {
                        hasValidationErrors = true;
                    }
                }
            });

            if (hasValidationErrors) {
                alert('無効な路線名があります。修正してください。');
                return; // 保存処理を中断
            }
            // --- バリデーション終了 ---

            // 路線
            const routesToSave = Array.from(routeInputs)
                .map(input => {
                    const lineName = input.value.trim();
                    if (lineName === '') return null;

                    let lineCd = input.dataset.lineCd || null;

                    // If line_cd is missing (manual input), try to find it
                    if (!lineCd) {
                        const foundRoute = allRoutes.find(route => route.line_name === lineName);
                        if (foundRoute) {
                            lineCd = foundRoute.line_cd;
                        }
                    }
                    return { line_name: lineName, line_cd: lineCd };
                })
                .filter(route => route !== null); // Filter out empty rows

            // 曜日
            const dayCheckboxes = dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)');
            const selectedDays = Array.from(dayCheckboxes)
                .filter(checkbox => checkbox.checked)
                .map(checkbox => checkbox.value);

            const payload = {
                lineUserId: lineUserId,
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

    /**
     * ルート入力のバリデーションを行い、UIを更新する
     * @param {HTMLElement} inputElement - バリデーション対象のinput要素
     * @returns {boolean} 入力が有効であればtrue、無効であればfalse
     */
    function validateRouteInput(inputElement) {
        const lineName = inputElement.value.trim();
        const routeRow = inputElement.closest('.route-row');

        if (lineName === '') {
            // 空の場合はエラーなし
            inputElement.classList.remove('invalid');
            routeRow.classList.remove('has-error');
            return true;
        }

        const isValid = allRoutes.some(route => route.line_name === lineName);

        if (isValid) {
            inputElement.classList.remove('invalid');
            routeRow.classList.remove('has-error');
        } else {
            inputElement.classList.add('invalid');
            routeRow.classList.add('has-error');
        }
        return isValid;
    }

    // --- すべての準備が整ったので、メイン処理を実行 ---
    main();
});