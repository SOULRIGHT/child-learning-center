(function () {
    const CYCLE = [
        '성장 데이터를 차근차근 정리하고 있어요...',
        'AI가 기록의 흐름을 살펴보고 있어요...',
        '해석에 잘못된 사실이 없는지 확인하고 있어요...',
        '안전하게 보여드릴 수 있는 내용인지 확인하고 있어요...'
    ];
    const CYCLE_MS = 1800;

    function config() {
        const node = document.getElementById('growth-ai-config');
        if (!node) return null;
        try {
            return JSON.parse(node.textContent);
        } catch (err) {
            return null;
        }
    }

    function panel(name) {
        return document.querySelector('[data-ai-panel="' + name + '"]');
    }

    function showState(state) {
        const card = document.getElementById('growth-ai-card');
        if (card) card.setAttribute('data-ai-state', state);
        document.querySelectorAll('[data-ai-panel]').forEach(function (el) {
            const match = el.getAttribute('data-ai-panel') === state
                || (state === 'timeout' && el.getAttribute('data-ai-panel') === 'error');
            el.classList.toggle('growth-ai-hidden', !match);
        });
    }

    function setDisabled(disabled) {
        document.querySelectorAll('[data-ai-action="generate"]').forEach(function (btn) {
            btn.disabled = disabled;
        });
    }

    function fillList(selector, items) {
        const node = document.querySelector(selector);
        if (!node) return;
        node.innerHTML = '';
        (items || []).forEach(function (text) {
            const li = document.createElement('li');
            li.textContent = text;
            node.appendChild(li);
        });
    }

    function fillEvidence(rows) {
        const node = document.querySelector('[data-ai-role="evidence"]');
        const summary = document.querySelector('[data-ai-role="evidence-summary"]');
        if (!node) return;
        node.innerHTML = '';
        (rows || []).forEach(function (row) {
            const dt = document.createElement('dt');
            dt.className = 'col-5';
            dt.textContent = row.label || '';
            const dd = document.createElement('dd');
            dd.className = 'col-7';
            dd.textContent = row.value || '';
            if (row.note) {
                const hint = document.createElement('div');
                hint.className = 'growth-ai-hint';
                hint.textContent = row.note;
                dd.appendChild(hint);
            }
            node.appendChild(dt);
            node.appendChild(dd);
        });
        if (summary) summary.textContent = '분석 근거 ' + (rows ? rows.length : 0) + '개 · 보기';
    }

    function renderSuccess(payload, freshlyReady) {
        const interpretation = payload.interpretation || {};
        const summary = document.querySelector('[data-ai-role="summary"]');
        if (summary) summary.textContent = interpretation.summary || '';
        fillList('[data-ai-role="observations"]', interpretation.observations || []);
        fillList('[data-ai-role="suggestions"]', interpretation.suggestions || []);
        const obsWrap = document.querySelector('[data-ai-role="observations-wrap"]');
        const sugWrap = document.querySelector('[data-ai-role="suggestions-wrap"]');
        if (obsWrap) obsWrap.classList.toggle('growth-ai-hidden', !(interpretation.observations || []).length);
        if (sugWrap) sugWrap.classList.toggle('growth-ai-hidden', !(interpretation.suggestions || []).length);
        fillEvidence(payload.evidence || []);
        const feedback = document.querySelector('[data-ai-role="feedback"]');
        if (feedback && payload.generation_id) {
            feedback.setAttribute('data-generation-id', String(payload.generation_id));
        }
        const ready = document.querySelector('[data-ai-role="ready"]');
        if (ready) ready.classList.toggle('growth-ai-hidden', !freshlyReady);
        showState('success');
    }

    document.addEventListener('DOMContentLoaded', function () {
        const cfg = config();
        const card = document.getElementById('growth-ai-card');
        if (!cfg || !card) return;

        let cycleTimer = null;
        let cycleIndex = 0;

        function stopCycle() {
            if (cycleTimer) {
                window.clearInterval(cycleTimer);
                cycleTimer = null;
            }
        }

        function startCycle() {
            const node = document.querySelector('[data-ai-role="cycle"]');
            cycleIndex = 0;
            if (node) node.textContent = CYCLE[0];
            const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            if (reduce) return;
            cycleTimer = window.setInterval(function () {
                cycleIndex = (cycleIndex + 1) % CYCLE.length;
                if (node) node.textContent = CYCLE[cycleIndex];
            }, CYCLE_MS);
        }

        async function generate() {
            setDisabled(true);
            showState('loading');
            startCycle();
            const controller = new AbortController();
            const timeoutMs = Number(cfg.timeoutMs) || 21000;
            const timer = window.setTimeout(function () { controller.abort(); }, timeoutMs);
            try {
                let url = cfg.generateUrl;
                if (cfg.asOf) {
                    url += (url.indexOf('?') >= 0 ? '&' : '?') + 'as_of=' + encodeURIComponent(cfg.asOf);
                }
                const response = await fetch(url, {
                    method: 'POST',
                    headers: { 'Accept': 'application/json' },
                    credentials: 'same-origin',
                    signal: controller.signal
                });
                const payload = await response.json();
                stopCycle();
                setDisabled(false);
                if (payload && payload.ok && payload.state === 'success') {
                    renderSuccess(payload, true);
                    return;
                }
                const state = (payload && payload.state) || 'error';
                if (state === 'quota' || state === 'stale' || state === 'disabled' || state === 'in_progress') {
                    if (state === 'stale' && payload.message) {
                        const msg = document.querySelector('[data-ai-role="stale-message"]');
                        if (msg) msg.textContent = payload.message;
                    }
                    showState(state === 'in_progress' ? 'loading' : state);
                    if (state === 'in_progress') startCycle();
                    return;
                }
                const errorNode = document.querySelector('[data-ai-role="error-message"]');
                if (errorNode && payload && payload.message) errorNode.textContent = payload.message;
                showState(state === 'timeout' ? 'timeout' : 'error');
            } catch (err) {
                stopCycle();
                setDisabled(false);
                const errorNode = document.querySelector('[data-ai-role="error-message"]');
                if (errorNode) {
                    errorNode.textContent = 'AI 해석 준비 시간이 조금 길어졌어요.\n다시 시도해주세요.';
                }
                showState('timeout');
            } finally {
                window.clearTimeout(timer);
            }
        }

        async function sendFeedback(helpful, comment) {
            const box = document.querySelector('[data-ai-role="feedback"]');
            const generationId = box && box.getAttribute('data-generation-id');
            if (!generationId) return;
            const body = { generation_id: Number(generationId), helpful: helpful };
            if (comment) body.comment = comment;
            await fetch(cfg.feedbackUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify(body)
            });
        }

        card.addEventListener('click', function (event) {
            const action = event.target.getAttribute('data-ai-action');
            if (action === 'generate') {
                generate();
            } else if (action === 'helpful-yes') {
                sendFeedback(true, null);
                const done = document.querySelector('[data-ai-role="feedback-done"]');
                if (done) done.classList.remove('growth-ai-hidden');
            } else if (action === 'helpful-no') {
                const form = document.querySelector('[data-ai-role="feedback-form"]');
                if (form) form.classList.remove('growth-ai-hidden');
            } else if (action === 'feedback-submit') {
                const area = document.getElementById('growth-ai-comment');
                sendFeedback(false, area ? area.value : '');
                const done = document.querySelector('[data-ai-role="feedback-done"]');
                if (done) done.classList.remove('growth-ai-hidden');
            }
        });
    });
})();
