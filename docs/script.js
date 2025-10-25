/**
 * 路線遅延通知システム フロントエンドスクリプト
 *
 * このスクリプトは、ユーザーの設定画面のすべての対話的処理を管理します。
 * 主な機能:
 * - LINEの認証コードを用いてユーザー情報を取得
 * - ユーザーの既存設定（路線、通知時間など）をフォームに表示
 * - 路線入力の自動補完機能
 * - 設定の追加、削除、保存
 */

// DOMの読み込みが完了した時点で処理を開始
document.addEventListener('DOMContentLoaded', async () => {

  // --- グローバル変数定義 ---

  // HTMLから操作対象の要素を取得
  const routeListContainer = document.getElementById('routeListContainer');
  const addRowButton = document.getElementById('addRowButton');
  const saveButton = document.getElementById('saveButton');
  const messageArea = document.getElementById('messageArea');
  const messageText = document.getElementById('messageText');
  const formContainer = document.getElementById('formContainer');
  const startTimeInput = document.getElementById('startTime');
  const endTimeInput = document.getElementById('endTime');
  const allDayCheckbox = document.getElementById('allDayCheckbox');
  const timeInputs = document.getElementById('timeInputs');
  const dayOfWeekContainer = document.getElementById('dayOfWeekContainer');

  // アプリケーション全体で利用する定数と変数
  const MAX_ROUTES = 5; // 登録可能な最大路線数
  let lineUserId = null; // ログインしたユーザーのLINE User ID
  let allRoutes = []; // 自動補完用の全路線リスト

  /**
   * メイン処理
   * ページの読み込み時に実行され、全体の処理フローを制御します。
   */
  async function main() {
    // 1. 路線リストをサーバーから非同期で読み込み、自動補完の準備をする
    await loadAllRoutes();

    // 2. URLのクエリパラメータからLINEの認証コードを取得
    const params = new URLSearchParams(window.location.search);
    const authCode = params.get('code');

    // 認証コードがない場合はエラーを表示して処理を中断
    if (!authCode) {
      displayMessage('エラー: ログイン情報が見つかりません。LINEのリッチメニューから再度アクセスしてください。', true);
      return;
    }

    // 3. 認証コードをバックエンド (AWS Lambda) に送信し、ユーザー情報を取得
    const userData = await getUserDataFromLambda(authCode);

    // ユーザー情報が正常に取得できた場合
    if (userData && userData.lineUserId) {
      lineUserId = userData.lineUserId; // ユーザーIDをグローバル変数に保存

      // 4. 取得したユーザー設定でフォームを初期化
      initializeSettings(userData);

      // 5. ローディングメッセージを非表示にし、設定フォームを表示
      formContainer.style.display = 'block';
      messageArea.style.display = 'none';

    } else {
      // ユーザー情報が取得できなかった場合
      console.error('取得したユーザーデータが不正です:', userData);
      displayMessage('エラー: ユーザー情報の取得に失敗しました。時間をおいて再度お試しください。', true);
    }

    // 6. すべてのボタンや入力欄にイベントリスナーを設定
    setupEventListeners();
  }

  /**
   * ユーザー情報取得
   * AWS Lambdaに認証コードを送信し、ユーザーIDや登録済みの設定を取得します。
   * @param {string} code - LINEから発行された認証コード
   * @returns {Promise<object|null>} 成功時はユーザーデータ、失敗時はnull
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
      return data;

    } catch (error) {
      console.error('Lambdaへのリクエストに失敗しました:', error);
      return null;
    }
  }

  /**
   * 全路線リストの読み込み
   * `routes.json`から自動補完に使用する路線名のリストを読み込みます。
   */
  async function loadAllRoutes() {
    try {
      const response = await fetch('routes.json');
      if (!response.ok) throw new Error('路線リストの取得に失敗');
      allRoutes = await response.json();
    } catch (error) {
      console.error('routes.jsonの読み込みエラー:', error);
      // 路線リストがなくてもアプリの他の機能は動作を続ける
    }
  }

  /**
   * フォームの初期化
   * 取得したユーザーデータに基づいて、フォームの各入力欄に値を設定します。
   * @param {object} userData - バックエンドから取得したユーザー設定データ
   */
  function initializeSettings(userData) {
    // デストラクチャリングとデフォルト値の設定
    const {
      routes = [],
      notificationStartTime = '07:00',
      notificationEndTime = '09:00',
      isAllDay = false,
      notificationDays = ['mon', 'tue', 'wed', 'thu', 'fri'] // デフォルトは平日
    } = userData;

    // 時間帯設定を反映
    startTimeInput.value = notificationStartTime;
    endTimeInput.value = notificationEndTime;
    allDayCheckbox.checked = isAllDay;
    timeInputs.style.display = isAllDay ? 'none' : '';

    // 曜日設定を反映
    const dayCheckboxes = dayOfWeekContainer.querySelectorAll('input[type="checkbox"]');
    dayCheckboxes.forEach(checkbox => {
      checkbox.checked = notificationDays.includes(checkbox.value);
    });

    // 「毎日」チェックボックスの状態を更新
    const dayEveryCheckbox = document.getElementById('dayEvery');
    const individualDayCheckboxes = Array.from(dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)'));
    dayEveryCheckbox.checked = individualDayCheckboxes.length > 0 && individualDayCheckboxes.every(cb => cb.checked);

    // 路線リストをクリアしてから、登録済みの路線をフォームに追加
    routeListContainer.innerHTML = '';
    if (routes.length > 0) {
      routes.forEach(route => {
        const routeRow = createRouteRow(route);
        routeListContainer.appendChild(routeRow);
      });
    } else {
      // 登録路線がない場合は、空の入力欄を1つ表示
      routeListContainer.appendChild(createRouteRow(''));
    }
  }

  /**
   * 路線入力行の生成
   * 路線名入力欄、候補表示ボタン、削除ボタンを含むHTML要素を生成します。
   * @param {object|string} routeData - 表示する路線データ（路線名と路線コード）
   * @returns {HTMLElement} 生成されたdiv要素
   */
  function createRouteRow(routeData = { line_name: '', line_cd: '' }) {
    const row = document.createElement('div');
    row.className = 'route-row';

    const wrapper = document.createElement('div');
    wrapper.className = 'route-input-wrapper';

    const autocompleteWrapper = document.createElement('div');
    autocompleteWrapper.className = 'autocomplete-wrapper';

    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'route-input';
    input.placeholder = '路線名を入力';

    // 路線データを入力欄に設定
    const routeName = typeof routeData === 'string' ? routeData : routeData.line_name;
    const routeCode = typeof routeData === 'string' ? '' : routeData.line_cd;
    input.value = routeName;
    if (routeCode) {
      input.dataset.lineCd = routeCode; // 路線コードをdata属性に保持
    }

    const suggestionsList = document.createElement('div');
    suggestionsList.className = 'suggestions-list';
    suggestionsList.style.display = 'none'; // 初期状態は非表示

    const dropdownButton = document.createElement('button');
    dropdownButton.className = 'dropdown-button';
    dropdownButton.innerHTML = '&#9660;'; // 下向き矢印

    // ドロップダウンボタンクリックで候補リストの表示/非表示を切り替え
    dropdownButton.addEventListener('click', (e) => {
      e.preventDefault();
      if (suggestionsList.style.display === 'none') {
        showSuggestions(input, suggestionsList, true); // 全件表示
      } else {
        suggestionsList.style.display = 'none';
      }
    });

    // フォーカス時に候補を表示
    input.addEventListener('focus', () => {
      if (input.value.trim() === '') {
        showSuggestions(input, suggestionsList, true);
      }
    });

    // フォーカスが外れたら少し遅れて候補を非表示（候補クリックを可能にするため）
    input.addEventListener('blur', () => {
      setTimeout(() => {
        if (!suggestionsList.contains(document.activeElement)) {
          suggestionsList.style.display = 'none';
        }
      }, 100);
    });

    // 入力中に候補を動的に表示
    input.addEventListener('input', () => {
      delete input.dataset.lineCd; // 手入力されたら路線コードをクリア
      showSuggestions(input, suggestionsList);
    });

    const deleteButton = document.createElement('button');
    deleteButton.textContent = '-';
    deleteButton.className = 'delete-row-btn';
    deleteButton.addEventListener('click', () => row.remove());

    // 各要素を組み立てて行を完成させる
    autocompleteWrapper.appendChild(input);
    autocompleteWrapper.appendChild(dropdownButton);
    autocompleteWrapper.appendChild(suggestionsList);

    wrapper.appendChild(autocompleteWrapper);
    row.appendChild(wrapper);
    row.appendChild(deleteButton);
    return row;
  }

  /**
   * 自動補完の候補リスト表示
   * 入力内容に基づいて、`allRoutes`から一致する路線を検索し、候補として表示します。
   * @param {HTMLInputElement} inputElement - 入力中のinput要素
   * @param {HTMLElement} suggestionsListElement - 候補リストを表示するdiv要素
   * @param {boolean} forceShow - trueの場合、入力が空でも候補を表示
   */
  function showSuggestions(inputElement, suggestionsListElement, forceShow = false) {
    const value = inputElement.value.trim();
    suggestionsListElement.innerHTML = '';

    let suggestions = [];
    if (value.length === 0 && forceShow) {
      suggestions = allRoutes.slice(0, 20); // 入力がない場合は先頭20件を表示
    } else if (value.length > 0) {
      suggestions = allRoutes.filter(route => route.line_name.includes(value)).slice(0, 10);
    }

    if (suggestions.length === 0) {
      suggestionsListElement.style.display = 'none';
      return;
    }

    // 候補リストの各項目を生成
    suggestions.forEach(suggestion => {
      const item = document.createElement('div');
      item.className = 'suggestion-item';
      item.textContent = suggestion.line_name;
      // 候補クリック時の処理
      item.addEventListener('mousedown', () => {
        inputElement.value = suggestion.line_name;
        inputElement.dataset.lineCd = suggestion.line_cd; // 路線コードをセット
        suggestionsListElement.style.display = 'none';
      });
      suggestionsListElement.appendChild(item);
    });
    suggestionsListElement.style.display = 'block';
  }

  /**
   * イベントリスナーの設定
   * ページ内のすべての対話要素にイベントハンドラを割り当てます。
   */
  function setupEventListeners() {
    // 「全時間帯」チェックボックスの変更イベント
    allDayCheckbox.addEventListener('change', () => {
      timeInputs.style.display = allDayCheckbox.checked ? 'none' : '';
    });

    // 「毎日」チェックボックスの変更イベント
    const dayEveryCheckbox = document.getElementById('dayEvery');
    const individualDayCheckboxes = Array.from(dayOfWeekContainer.querySelectorAll('.dow-checkboxes input[type="checkbox"]:not(#dayEvery)'));

    dayEveryCheckbox.addEventListener('change', () => {
      individualDayCheckboxes.forEach(checkbox => {
        checkbox.checked = dayEveryCheckbox.checked;
      });
    });

    // 各曜日のチェックボックスの変更イベント
    individualDayCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        dayEveryCheckbox.checked = individualDayCheckboxes.every(cb => cb.checked);
      });
    });

    // 保存ボタンのクリックイベント
    saveButton.addEventListener('click', async () => {
      // --- 入力値のバリデーション ---
      const routeInputs = document.querySelectorAll('.route-input');
      const routesToValidate = Array.from(routeInputs)
        .map(input => {
          const lineName = input.value.trim();
          if (lineName === '') return null; // 空の入力は無視

          // 候補から選択されているか、または手入力が完全一致するか
          const isSelectedFromDropdown = !!input.dataset.lineCd;
          const isExactMatchInAllRoutes = allRoutes.some(route => route.line_name === lineName);

          if (!(isSelectedFromDropdown && isExactMatchInAllRoutes)) {
            return lineName; // 無効な路線名を収集
          }
          return null;
        })
        .filter(name => name !== null);

      if (routesToValidate.length > 0) {
        alert(`以下の路線は登録できません。候補から選択してください。
${routesToValidate.join('
')}`);
        return; // バリデーションエラーがあれば保存を中断
      }

      // --- 保存データの準備 ---
      const routesToSave = Array.from(routeInputs)
        .map(input => {
          const lineName = input.value.trim();
          if (lineName === '') return null;

          let lineCd = input.dataset.lineCd || null;
          // 路線コードがない場合、路線名から再検索
          if (!lineCd) {
            const foundRoute = allRoutes.find(route => route.line_name === lineName);
            if (foundRoute) lineCd = foundRoute.line_cd;
          }
          return { line_name: lineName, line_cd: lineCd };
        })
        .filter(route => route !== null);

      const selectedDays = Array.from(dayOfWeekContainer.querySelectorAll('.dow-checkboxes input:checked'))
        .map(checkbox => checkbox.value);

      // バックエンドに送信するデータ（ペイロード）
      const payload = {
        lineUserId: lineUserId,
        routes: routesToSave,
        notificationStartTime: startTimeInput.value,
        notificationEndTime: endTimeInput.value,
        isAllDay: allDayCheckbox.checked,
        notificationDays: selectedDays
      };

      displayMessage('保存中...', false);
      formContainer.style.display = 'none';

      // --- バックエンドへの保存リクエスト ---
      try {
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
        // 1.5秒後にメッセージを消してフォームを再表示
        setTimeout(() => {
          messageArea.style.display = 'none';
          formContainer.style.display = 'block';
        }, 1500);
      }
    });

    // 路線追加ボタンのクリックイベント
    addRowButton.addEventListener('click', () => {
      if (routeListContainer.childElementCount < MAX_ROUTES) {
        routeListContainer.appendChild(createRouteRow(''));
      } else {
        alert(`登録できる路線は${MAX_ROUTES}つまでです。`);
      }
    });

    // ページ全体でクリックを監視し、候補リスト以外がクリックされたらリストを閉じる
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.route-input-wrapper')) {
        document.querySelectorAll('.suggestions-list').forEach(list => list.style.display = 'none');
      }
    });
  }

  /**
   * メッセージ表示
   * 画面上部に操作結果などのメッセージを表示します。
   * @param {string} text - 表示するメッセージ文字列
   * @param {boolean} isError - エラーメッセージかどうか（trueなら赤字表示）
   */
  function displayMessage(text, isError) {
    messageArea.style.display = 'block';
    messageText.textContent = text;
    messageText.style.color = isError ? 'red' : 'black';
    if (isError) {
      formContainer.style.display = 'none'; // エラー時はフォームを非表示にする
    }
  }

  // --- メイン処理の実行 ---
  main();
});
