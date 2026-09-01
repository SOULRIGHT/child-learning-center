(function () {
    const CYCLE = [
        '성장 데이터를 차근차근 정리하고 있어요...',
        'AI가 기록의 흐름을 살펴보고 있어요...',
        '해석에 잘못된 사실이 없는지 확인하고 있어요...',
        '안전하게 보여드릴 수 있는 내용인지 확인하고 있어요...'
    ];
    const STAGE_KEYS = ['organize', 'interpret', 'verify', 'safety'];
    const STAGE_MS = 1500;
    const MIN_HOLD_MS = 6000;
    const STAGE_COUNT = 4;

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

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function setPresentationStage(name) {
        const card = document.getElementById('growth-ai-card');
        if (card) card.setAttribute('data-stage', name);
        document.querySelectorAll('[data-ai-role="mascot-slot"]').forEach(function (el) {
            el.setAttribute('data-stage', name);
        });
    }

    function applyFocus(index) {
        const bounded = Math.max(0, Math.min(STAGE_COUNT - 1, index));
        const card = document.getElementById('growth-ai-card');
        if (card) card.setAttribute('data-ai-focus-step', String(bounded));
        document.querySelectorAll('[data-ai-step]').forEach(function (el) {
            const step = Number(el.getAttribute('data-ai-step'));
            el.classList.toggle('is-focus', step === bounded);
            el.classList.remove('is-done', 'is-complete');
            el.removeAttribute('data-complete');
        });
        document.querySelectorAll('[data-ai-mascot-scene]').forEach(function (el) {
            const step = Number(el.getAttribute('data-ai-mascot-scene'));
            el.classList.toggle('is-focus', step === bounded);
        });
        const node = document.querySelector('[data-ai-role="cycle"]');
        if (node) node.textContent = CYCLE[bounded] || CYCLE[0];
        setPresentationStage(STAGE_KEYS[bounded] || STAGE_KEYS[0]);
    }

    function setWaitingVisible(visible) {
        const waiting = document.querySelector('[data-ai-role="waiting"]');
        if (waiting) waiting.classList.toggle('growth-ai-hidden', !visible);
        if (visible) setPresentationStage('waiting');
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

    function setSection(selector, visible) {
        const node = document.querySelector(selector);
        if (node) node.classList.toggle('growth-ai-hidden', !visible);
    }

    function appendHint(parent, note) {
        if (!note) return;
        const hint = document.createElement('div');
        hint.className = 'growth-ai-hint';
        hint.textContent = note;
        parent.appendChild(hint);
    }

    function fillDl(node, rows, dtClass, ddClass) {
        node.innerHTML = '';
        (rows || []).forEach(function (row) {
            const dt = document.createElement('dt');
            if (dtClass) dt.className = dtClass;
            dt.textContent = row.label || '';
            const dd = document.createElement('dd');
            if (ddClass) dd.className = ddClass;
            dd.textContent = row.value || '';
            appendHint(dd, row.note);
            node.appendChild(dt);
            node.appendChild(dd);
        });
    }

    function fillEvidence(rows, groups) {
        const fallback = document.querySelector('[data-ai-role="evidence"]');
        const title = document.querySelector('[data-ai-role="evidence-title"]');
        const chips = document.querySelector('[data-ai-role="evidence-chips"]');
        const block = document.querySelector('[data-ai-role="evidence-block"]');
        const groupRoot = document.querySelector('[data-ai-role="evidence-groups"]');
        const items = groups && Array.isArray(groups.items) ? groups.items : (rows || []);
        const total = groups && typeof groups.total === 'number' ? groups.total : items.length;
        if (title) title.textContent = '분석 근거 ' + total + '개';
        if (chips) chips.textContent = (groups && groups.chips) || '';
        if (block) block.classList.toggle('growth-ai-hidden', !total);
        if (fallback) fillDl(fallback, items, 'col-5', 'col-7');
        if (!groupRoot) return;
        groupRoot.innerHTML = '';
        const groupList = (groups && groups.groups) || [];
        groupList.forEach(function (group) {
            const wrap = document.createElement('details');
            wrap.className = 'growth-ai-evidence-group';
            wrap.setAttribute('data-ai-group', '');
            const summary = document.createElement('summary');
            summary.appendChild(document.createTextNode(group.label + ' '));
            const count = document.createElement('span');
            count.className = 'growth-ai-hint';
            count.textContent = String(group.count || 0) + '개';
            summary.appendChild(count);
            wrap.appendChild(summary);
            if (group.compact && group.compact.length) {
                const compact = document.createElement('dl');
                compact.className = 'growth-ai-compact';
                fillDl(compact, group.compact);
                wrap.appendChild(compact);
            }
            if (group.note) {
                const note = document.createElement('p');
                note.className = 'growth-ai-hint';
                note.textContent = group.note;
                wrap.appendChild(note);
            }
            const inner = document.createElement('details');
            inner.className = 'growth-ai-evidence-items';
            const innerSummary = document.createElement('summary');
            innerSummary.textContent = '개별 근거 모두 보기';
            inner.appendChild(innerSummary);
            const list = document.createElement('dl');
            list.className = 'growth-ai-evidence-list';
            fillDl(list, group.items || []);
            inner.appendChild(list);
            wrap.appendChild(inner);
            groupRoot.appendChild(wrap);
        });
        if (!groupList.length && items.length) {
            const list = document.createElement('dl');
            list.className = 'growth-ai-evidence-list';
            fillDl(list, items);
            groupRoot.appendChild(list);
        }
    }

    function renderSuccess(payload, freshlyReady) {
        const interpretation = payload.interpretation || {};
        const summary = document.querySelector('[data-ai-role="summary"]');
        if (summary) summary.textContent = interpretation.priority_insight || interpretation.summary || '';
        const meaning = document.querySelector('[data-ai-role="interpretation"]');
        if (meaning) meaning.textContent = interpretation.interpretation || '';
        setSection('[data-ai-role="interpretation-wrap"]', !!(interpretation.interpretation || '').trim());
        fillList('[data-ai-role="observations"]', interpretation.observations || []);
        fillList('[data-ai-role="suggestions"]', interpretation.next_actions || interpretation.suggestions || []);
        const nextCheck = document.querySelector('[data-ai-role="next-check"]');
        if (nextCheck) nextCheck.textContent = interpretation.next_check || '';
        setSection('[data-ai-role="observations-wrap"]', (interpretation.observations || []).length > 0);
        setSection('[data-ai-role="suggestions-wrap"]', (interpretation.next_actions || interpretation.suggestions || []).length > 0);
        setSection('[data-ai-role="next-check-wrap"]', !!(interpretation.next_check || '').trim());
        fillEvidence(payload.evidence || [], payload.evidence_groups || null);
        const feedback = document.querySelector('[data-ai-role="feedback"]');
        if (feedback && payload.generation_id) {
            feedback.setAttribute('data-generation-id', String(payload.generation_id));
        }
        const ready = document.querySelector('[data-ai-role="ready"]');
        if (ready) ready.classList.toggle('growth-ai-hidden', !freshlyReady);
        showState('success');
    }

    function isPreflight(payload) {
        if (!payload) return false;
        if (payload.started === true) return false;
        const state = payload.state;
        return state === 'disabled' || state === 'quota' || state === 'in_progress'
            || (state === 'success' && payload.cached === true)
            || payload.started === false;
    }

    document.addEventListener('DOMContentLoaded', function () {
        const cfg = config();
        const card = document.getElementById('growth-ai-card');
        if (!cfg || !card) return;

        let stageTimers = [];
        let presentation = null;

        function clearStageTimers() {
            stageTimers.forEach(function (id) { window.clearTimeout(id); });
            stageTimers = [];
        }

        function stopPresentation() {
            clearStageTimers();
            presentation = null;
            setWaitingVisible(false);
        }

        function startPresentation() {
            stopPresentation();
            const startedAt = Date.now();
            presentation = {
                startedAt: startedAt,
                holdDone: false,
                payload: null,
                reducedMotion: prefersReducedMotion()
            };
            applyFocus(0);
            setWaitingVisible(false);
            for (let i = 1; i < STAGE_COUNT; i += 1) {
                stageTimers.push(window.setTimeout(function (step) {
                    if (!presentation) return;
                    applyFocus(step);
                }, STAGE_MS * i, i));
            }
            stageTimers.push(window.setTimeout(function () {
                if (!presentation) return;
                presentation.holdDone = true;
                if (!presentation.payload) {
                    applyFocus(STAGE_COUNT - 1);
                    setWaitingVisible(true);
                    return;
                }
                reveal(presentation.payload);
            }, MIN_HOLD_MS));
        }

        function reveal(payload) {
            stopPresentation();
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
                if (state === 'in_progress') {
                    showState('loading');
                    applyFocus(0);
                    return;
                }
                showState(state);
                return;
            }
            const errorNode = document.querySelector('[data-ai-role="error-message"]');
            if (errorNode && payload && payload.message) errorNode.textContent = payload.message;
            showState(state === 'timeout' ? 'timeout' : 'error');
        }

        function settle(payload) {
            if (isPreflight(payload)) {
                reveal(payload);
                return;
            }
            if (!presentation) {
                reveal(payload);
                return;
            }
            presentation.payload = payload;
            if (presentation.holdDone) {
                reveal(payload);
            }
        }

        async function generate() {
            setDisabled(true);
            showState('loading');
            startPresentation();
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
                settle(payload);
            } catch (err) {
                settle({
                    ok: false,
                    started: true,
                    state: 'timeout',
                    message: 'AI 해석 준비 시간이 조금 길어졌어요.\n다시 시도해주세요.'
                });
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
            } else if (action === 'expand-all-evidence') {
                card.querySelectorAll('[data-ai-role="evidence-wrap"], [data-ai-group], .growth-ai-evidence-items').forEach(function (node) {
                    node.open = true;
                });
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
