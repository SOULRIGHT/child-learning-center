(function () {
    const STORAGE_KEY = 'clc.teacherAssistant.v2';
    const STAGE_EL = '[data-assistant-role="character-stage"]';
    const QUESTION_LIMIT_DEFAULT = 10;

    function boot() {
        const node = document.getElementById('assistant-page-context');
        if (!node) return null;
        try {
            return JSON.parse(node.textContent);
        } catch (err) {
            return null;
        }
    }

    function emptyState(scope) {
        return {
            version: 1,
            drawerOpen: false,
            childId: null,
            storageScope: scope || '',
            questionCount: 0,
            generalMessages: [],
            childMessages: [],
            conversation: {},
        };
    }

    function compactConversation(raw) {
        if (!raw || typeof raw !== 'object') return {};
        const out = {};
        if (raw.active_child_id != null && raw.active_child_id !== '') {
            const id = Number(raw.active_child_id);
            if (!Number.isNaN(id)) out.active_child_id = id;
        }
        if (raw.active_child_nickname) {
            out.active_child_nickname = String(raw.active_child_nickname).slice(0, 40);
        }
        if (raw.active_subject) out.active_subject = String(raw.active_subject).slice(0, 20);
        if (raw.active_topic) out.active_topic = String(raw.active_topic).slice(0, 20);
        if (raw.pending_action && typeof raw.pending_action === 'object') {
            const pending = {
                type: raw.pending_action.type || '',
                awaiting: raw.pending_action.awaiting || '',
            };
            if (raw.pending_action.destination) pending.destination = String(raw.pending_action.destination).slice(0, 40);
            if (raw.pending_action.tool) pending.tool = String(raw.pending_action.tool).slice(0, 40);
            if (Array.isArray(raw.pending_action.missing)) pending.missing = raw.pending_action.missing.slice(0, 4);
            if (raw.pending_action.candidate_child_id != null) {
                pending.candidate_child_id = Number(raw.pending_action.candidate_child_id);
            }
            if (raw.pending_action.candidate_nickname) {
                pending.candidate_nickname = String(raw.pending_action.candidate_nickname).slice(0, 40);
            }
            if (raw.pending_action.subject_key) pending.subject_key = String(raw.pending_action.subject_key).slice(0, 20);
            out.pending_action = pending;
        }
        return out;
    }

    function bindScope(state, scope) {
        if (!scope) {
            clearStored();
            return emptyState('');
        }
        if (state.storageScope !== scope) {
            clearStored();
            return emptyState(scope);
        }
        state.storageScope = scope;
        return state;
    }

    function clearStored() {
        try {
            sessionStorage.removeItem(STORAGE_KEY);
        } catch (err) {
            return;
        }
    }

    function loadState() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            if (!raw) return emptyState();
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.version !== 1) return emptyState();
            const count = Number(parsed.questionCount);
            return {
                version: 1,
                drawerOpen: Boolean(parsed.drawerOpen),
                childId: parsed.childId == null ? null : parsed.childId,
                storageScope: typeof parsed.storageScope === 'string' ? parsed.storageScope : '',
                questionCount: Number.isFinite(count) && count > 0 ? Math.min(count, 10) : 0,
                generalMessages: Array.isArray(parsed.generalMessages) ? parsed.generalMessages : [],
                childMessages: Array.isArray(parsed.childMessages) ? parsed.childMessages : [],
                conversation: compactConversation(parsed.conversation),
            };
        } catch (err) {
            return emptyState();
        }
    }

    function saveState(state) {
        try {
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
                version: 1,
                drawerOpen: Boolean(state.drawerOpen),
                childId: state.childId == null ? null : state.childId,
                storageScope: state.storageScope || '',
                questionCount: Number(state.questionCount) || 0,
                generalMessages: (state.generalMessages || []).slice(-24),
                childMessages: (state.childMessages || []).slice(-24),
                conversation: compactConversation(state.conversation),
            }));
        } catch (err) {
            return;
        }
    }

    function isolateChild(state, page) {
        const nextId = page && page.child_id != null ? page.child_id : null;
        state.childId = nextId;
        return state;
    }

    function isChildScoped(message) {
        return Boolean(message && message.context_scope && message.context_scope.child_id);
    }

    function visibleMessages(state) {
        return (state.generalMessages || []).concat(state.childMessages || []);
    }

    function storeMessage(state, message) {
        const copy = {
            role: message.role,
            content: message.content,
            kind: message.kind || (message.role === 'user' ? 'chat' : 'system'),
            context_scope: message.context_scope || {},
            actions: message.actions || [],
            sources: compactSources(message.sources),
        };
        if (message.request_id) copy.request_id = String(message.request_id).slice(0, 36);
        if (message.feedback_enabled) copy.feedback_enabled = true;
        if (isChildScoped(copy)) {
            state.childMessages.push(copy);
        } else {
            state.generalMessages.push(copy);
        }
    }

    function reclassifyLatestUser(state, page, kind) {
        if (!kind) return;
        const bucket = page && page.child_id
            ? state.childMessages
            : state.generalMessages;
        for (let index = bucket.length - 1; index >= 0; index -= 1) {
            if (bucket[index] && bucket[index].role === 'user') {
                bucket[index].kind = kind;
                return;
            }
        }
    }

    function compactSources(sources) {
        if (!Array.isArray(sources)) return [];
        return sources.slice(0, 12).map(function (source) {
            if (!source || typeof source !== 'object') return null;
            const item = {
                kind: source.kind === 'help' ? 'help' : 'data',
                label: source.label || '',
            };
            if (source.evidence_id) item.evidence_id = String(source.evidence_id).slice(0, 120);
            if (source.url) item.url = source.url;
            if (source.destination) item.destination = source.destination;
            if (typeof source.available === 'boolean') item.available = source.available;
            return item;
        }).filter(Boolean);
    }

    function fillCharacter(character) {
        const stage = document.querySelector(STAGE_EL);
        if (!stage) return;
        stage.innerHTML = '';
        if (!character || !character.url) {
            stage.classList.remove('is-filled');
            stage.hidden = true;
            return;
        }
        stage.classList.add('is-filled');
        stage.hidden = false;
        if (character.kind === 'video') {
            const video = document.createElement('video');
            video.src = character.url;
            video.muted = true;
            video.playsInline = true;
            video.setAttribute('aria-hidden', 'true');
            stage.appendChild(video);
            return;
        }
        const img = document.createElement('img');
        img.src = character.url;
        img.alt = '';
        stage.appendChild(img);
    }

    function qs(name, root) {
        return (root || document).querySelector('[data-assistant-role="' + name + '"]');
    }

    function setStage(name) {
        const stage = document.querySelector(STAGE_EL);
        if (!stage) return;
        stage.setAttribute('data-assistant-stage', name || 'idle');
        if (!stage.classList.contains('is-filled')) {
            stage.hidden = true;
        }
    }

    function showError(text) {
        const node = qs('error');
        const recovery = qs('recovery');
        if (!node) return;
        if (!text) {
            node.hidden = true;
            node.textContent = '';
            if (recovery) recovery.hidden = true;
            return;
        }
        node.hidden = false;
        node.textContent = typeof text === 'string' ? text : '응답을 가져오지 못했습니다.';
        if (recovery) recovery.hidden = false;
        setStage('error');
    }

    function renderOnboarding(status) {
        const node = qs('onboarding');
        if (!node) return;
        const onboarding = status && status.onboarding;
        if (!onboarding || !onboarding.available) {
            node.hidden = true;
            node.innerHTML = '';
            return;
        }
        const next = onboarding.next;
        let html = '<div class="assistant-onboarding-label">센터 설정 안내</div>';
        if (next) {
            html += '<div class="assistant-onboarding-next">현재 다음 권장: ' + escapeHtml(next.label || '') + '</div>';
            if (next.url) {
                html += '<div class="assistant-bubble-actions"><button type="button" class="assistant-action" data-assistant-nav="' + escapeAttr(next.url) + '">설정 화면 열기</button></div>';
            }
        } else {
            html += '<div class="assistant-onboarding-next">필요한 설정은 확인된 상태입니다.</div>';
        }
        node.innerHTML = html;
        node.hidden = false;
    }

    function questionLimit(config) {
        const n = Number(config && config.question_limit);
        return Number.isFinite(n) && n > 0 ? n : QUESTION_LIMIT_DEFAULT;
    }

    function renderCounter(state, config) {
        const node = qs('question-count');
        if (!node) return;
        const limit = questionLimit(config);
        const count = Number(state.questionCount) || 0;
        node.textContent = '대화 ' + count + ' / ' + limit;
    }

    function renderLimit(state, config) {
        const banner = qs('limit-banner');
        const limit = questionLimit(config);
        const reached = (Number(state.questionCount) || 0) >= limit;
        if (banner) banner.hidden = !reached;
        const input = qs('input');
        const sendBtn = qs('send');
        if (input) {
            input.disabled = reached;
            input.placeholder = reached ? '이번 대화의 질문을 모두 사용했습니다.' : '도움이 필요하면 적어 주세요';
        }
        if (sendBtn) sendBtn.disabled = reached;
    }

    function renderMessages(state) {
        const root = qs('conversation');
        if (!root) return;
        root.innerHTML = '';
        visibleMessages(state).forEach(function (message) {
            const wrap = document.createElement('div');
            wrap.className = 'assistant-bubble is-' + (message.role === 'user' ? 'user' : 'assistant');
            wrap.textContent = message.content || '';
            if (message.actions && message.actions.length) {
                const row = document.createElement('div');
                row.className = 'assistant-bubble-actions';
                message.actions.forEach(function (action) {
                    if (!action) return;
                    if (action.url) {
                        const btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'assistant-action';
                        btn.textContent = action.label || '열기';
                        btn.setAttribute('data-assistant-nav', action.url);
                        if (action.destination) {
                            btn.setAttribute('data-assistant-destination', action.destination);
                        }
                        if (action.params && action.params.child_id != null) {
                            btn.setAttribute('data-assistant-child-id', action.params.child_id);
                        }
                        row.appendChild(btn);
                        return;
                    }
                    if (action.type === 'reply' || action.content) {
                        const btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'assistant-action';
                        btn.textContent = action.label || action.content || '확인';
                        btn.setAttribute('data-assistant-reply', action.content || action.label || '');
                        row.appendChild(btn);
                    }
                });
                wrap.appendChild(row);
            }
            if (message.sources && message.sources.length) {
                const sources = document.createElement('div');
                sources.className = 'assistant-sources';
                sources.setAttribute('data-testid', 'assistant-sources');
                message.sources.forEach(function (source) {
                    if (!source) return;
                    const chip = document.createElement(source.url ? 'button' : 'span');
                    chip.className = 'assistant-source is-' + (source.kind === 'help' ? 'help' : 'data');
                    if (source.available === false) chip.classList.add('is-missing');
                    chip.textContent = (source.kind === 'help' ? '안내 · ' : '기록 · ') + (source.label || '');
                    if (source.url) {
                        chip.type = 'button';
                        chip.setAttribute('data-assistant-nav', source.url);
                    }
                    sources.appendChild(chip);
                });
                wrap.appendChild(sources);
            }
            if (message.role === 'assistant' && message.feedback_enabled && message.request_id) {
                const row = document.createElement('div');
                row.className = 'assistant-feedback';
                ['positive', 'negative'].forEach(function (rating) {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'assistant-feedback-btn';
                    btn.textContent = rating === 'positive' ? '👍' : '👎';
                    btn.setAttribute('aria-label', rating === 'positive' ? '도움됨' : '아쉬움');
                    btn.setAttribute('data-assistant-feedback', rating);
                    btn.setAttribute('data-assistant-request', message.request_id);
                    row.appendChild(btn);
                });
                wrap.appendChild(row);
            }
            root.appendChild(wrap);
        });
        root.scrollTop = root.scrollHeight;
    }

    function renderQuick(actions, hasTranscript) {
        const root = qs('quick-actions');
        if (!root) return;
        root.innerHTML = '';
        if (hasTranscript || !actions || !actions.length) return;
        actions.forEach(function (action) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'assistant-chip';
            btn.textContent = action.label || '';
            btn.setAttribute('data-assistant-quick', JSON.stringify(action));
            root.appendChild(btn);
        });
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    function intentKind(intent) {
        if (intent === 'navigate') return 'nav';
        if (intent === 'continue_setup') return 'onboarding';
        if (intent === 'explain_page' || intent === 'bootstrap') return 'system';
        return 'chat';
    }

    document.addEventListener('click', function (event) {
        const link = event.target.closest('a[href]');
        if (!link) return;
        const href = link.getAttribute('href') || '';
        if (href.indexOf('logout') !== -1) {
            try {
                sessionStorage.removeItem(STORAGE_KEY);
            } catch (err) {
                return;
            }
        }
    });

    function applyResponse(state, payload, page, config) {
        if (!payload) return;
        const rawMessage = payload.message;
        if (typeof rawMessage === 'string') {
            showError(rawMessage);
            return;
        }
        if (!rawMessage) return;
        const message = rawMessage;
        message.actions = payload.actions || [];
        message.sources = compactSources(payload.sources);
        message.kind = message.kind || (payload.feedback_enabled ? 'llm' : 'system');
        if (payload.feedback_enabled && payload.request_id) {
            message.feedback_enabled = true;
            message.request_id = payload.request_id;
        }
        if (payload.status && payload.status.conversation_state) {
            state.conversation = compactConversation(payload.status.conversation_state);
        }
        if (typeof payload.question_count === 'number') {
            state.questionCount = payload.question_count;
        }
        if (payload.last_user_kind) {
            reclassifyLatestUser(state, page, payload.last_user_kind);
        }
        storeMessage(state, message);
        saveState(state);
        renderMessages(state);
        renderOnboarding(payload.status);
        renderQuick(payload.quick_actions, visibleMessages(state).length > 0);
        renderCounter(state, config);
        renderLimit(state, config);
        setStage(payload.character_state || 'idle');
        showError('');
        const auto = (payload.actions || []).find(function (action) {
            return action && action.auto && action.url;
        });
        if (auto && auto.url) {
            window.location.assign(auto.url);
        }
    }

    function post(url, body) {
        return fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify(body),
        }).then(function (response) {
            return response.json().catch(function () {
                return { ok: false, message: '조교 응답을 가져오지 못했습니다. 기존 화면은 그대로 사용할 수 있어요.' };
            }).then(function (payload) {
                payload = payload || {};
                payload._httpStatus = response.status;
                return payload;
            });
        });
    }

    document.addEventListener('DOMContentLoaded', function () {
        try {
            initAssistant();
        } catch (err) {
            return;
        }
    });

    function initAssistant() {
        const config = boot();
        const drawer = document.getElementById('teacherAssistantDrawer');
        if (!config || !drawer || typeof bootstrap === 'undefined') return;

        const page = config.page || {};
        fillCharacter(config.character);
        let state = isolateChild(bindScope(loadState(), config.storage_scope || ''), page);
        let lastRequest = null;
        saveState(state);
        renderMessages(state);
        renderQuick(null, visibleMessages(state).length > 0);
        renderCounter(state, config);
        renderLimit(state, config);
        setStage('idle');

        const launcherEl = document.getElementById('teacherAssistantLauncher');
        const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(drawer);
        if (state.drawerOpen) {
            if (launcherEl) launcherEl.hidden = true;
            offcanvas.show();
        }

        function errorText(value) {
            if (typeof value === 'string' && value && value.indexOf('조교 응답을 가져오지 못했습니다') === -1) {
                return value;
            }
            return '응답을 가져오지 못했습니다.';
        }

        function bootstrapQuick() {
            return post(config.message_url, {
                intent: 'bootstrap',
                messages: [],
                page_context: page,
            }).then(function (payload) {
                if (payload._httpStatus >= 500) {
                    showError(errorText(payload.message));
                    return payload;
                }
                renderOnboarding(payload.status);
                const hasTranscript = visibleMessages(state).length > 0;
                renderQuick(payload.quick_actions, hasTranscript);
                const root = qs('conversation');
                if (root && !hasTranscript && !root.childNodes.length && payload.message && payload.message.content) {
                    const intro = document.createElement('div');
                    intro.className = 'assistant-bubble is-assistant';
                    intro.textContent = payload.message.content || '무엇을 도와드릴까요?';
                    root.appendChild(intro);
                }
                return payload;
            });
        }

        function resetConversation() {
            lastRequest = null;
            state.generalMessages = [];
            state.childMessages = [];
            state.questionCount = 0;
            state.conversation = page.child_id ? { active_child_id: page.child_id } : {};
            saveState(state);
            renderMessages(state);
            renderOnboarding(null);
            renderCounter(state, config);
            renderLimit(state, config);
            showError('');
            setStage('idle');
            bootstrapQuick().catch(function () {
                showError('응답을 가져오지 못했습니다.');
            });
        }

        function retryLast() {
            if (!lastRequest) {
                resetConversation();
                return;
            }
            setStage('thinking');
            showError('');
            post(config.message_url, lastRequest).then(function (response) {
                if (response._httpStatus >= 500) {
                    showError(errorText(response.message));
                    return;
                }
                applyResponse(state, response, page, config);
            }).catch(function () {
                showError('응답을 가져오지 못했습니다.');
            });
        }

        drawer.addEventListener('shown.bs.offcanvas', function () {
            state.drawerOpen = true;
            saveState(state);
            if (launcherEl) launcherEl.hidden = true;
            bootstrapQuick().catch(function () {
                showError('응답을 가져오지 못했습니다.');
            });
        });

        drawer.addEventListener('hidden.bs.offcanvas', function () {
            state.drawerOpen = false;
            saveState(state);
            if (launcherEl) launcherEl.hidden = false;
        });

        drawer.addEventListener('click', function (event) {
            const retry = event.target.closest('[data-assistant-role="retry"]');
            if (retry) {
                retryLast();
                return;
            }
            const reset = event.target.closest('[data-assistant-role="reset"], [data-assistant-role="new-conversation"]');
            if (reset) {
                resetConversation();
                return;
            }
            const nav = event.target.closest('[data-assistant-nav]');
            if (nav) {
                const url = nav.getAttribute('data-assistant-nav');
                const childId = Number(nav.getAttribute('data-assistant-child-id'));
                if (!Number.isNaN(childId) && childId > 0) {
                    state.conversation.active_child_id = childId;
                    state.conversation.pending_action = null;
                    const destination = nav.getAttribute('data-assistant-destination');
                    if (destination) state.conversation.active_topic = 'nav';
                    saveState(state);
                }
                if (url) window.location.assign(url);
                return;
            }
            const feedback = event.target.closest('[data-assistant-feedback]');
            if (feedback) {
                const rating = feedback.getAttribute('data-assistant-feedback');
                const requestId = feedback.getAttribute('data-assistant-request');
                if (!config.feedback_url || !requestId) return;
                post(config.feedback_url, { request_id: requestId, rating: rating }).then(function () {
                    const row = feedback.parentNode;
                    if (!row) return;
                    row.querySelectorAll('.assistant-feedback-btn').forEach(function (btn) {
                        btn.classList.toggle('is-selected', btn === feedback);
                    });
                }).catch(function () {
                    return;
                });
                return;
            }
            const reply = event.target.closest('[data-assistant-reply]');
            if (reply) {
                const text = (reply.getAttribute('data-assistant-reply') || '').trim();
                if (text) sendChat(text, 'confirm');
                return;
            }
            const quick = event.target.closest('[data-assistant-quick]');
            if (!quick) return;
            let action = null;
            try {
                action = JSON.parse(quick.getAttribute('data-assistant-quick') || '{}');
            } catch (err) {
                return;
            }
            sendIntent(action);
        });

        const form = qs('composer');
        const input = qs('input');
        const sendBtn = qs('send');

        function sendIntent(action) {
            const kind = intentKind(action.intent);
            const payload = {
                intent: action.intent || 'chat',
                destination: action.destination || null,
                params: action.params || {},
                messages: visibleMessages(state).concat([{
                    role: 'user',
                    content: action.label || action.intent || '',
                    kind: kind,
                    context_scope: { endpoint: page.endpoint || '', child_id: page.child_id || null },
                }]),
                page_context: page,
                conversation_state: compactConversation(state.conversation),
            };
            lastRequest = payload;
            storeMessage(state, payload.messages[payload.messages.length - 1]);
            saveState(state);
            renderMessages(state);
            renderQuick(null, true);
            setStage('thinking');
            post(config.message_url, payload).then(function (response) {
                if (response._httpStatus >= 500 || response.ok === false && !response.message) {
                    showError(errorText(response && response.message));
                    return;
                }
                applyResponse(state, response, page, config);
            }).catch(function () {
                showError('응답을 가져오지 못했습니다.');
            });
        }

        function sendChat(text, kind) {
            kind = kind || 'chat';
            if (kind === 'chat' && (Number(state.questionCount) || 0) >= questionLimit(config)) {
                renderLimit(state, config);
                return Promise.resolve();
            }
            const userMessage = {
                role: 'user',
                content: text,
                kind: kind,
                context_scope: { endpoint: page.endpoint || '', child_id: page.child_id || null },
            };
            const payload = {
                intent: 'chat',
                messages: visibleMessages(state).concat([userMessage]),
                page_context: page,
                conversation_state: compactConversation(state.conversation),
            };
            lastRequest = payload;
            storeMessage(state, userMessage);
            saveState(state);
            renderMessages(state);
            renderQuick(null, true);
            setStage('thinking');
            return post(config.message_url, payload).then(function (response) {
                if (response._httpStatus >= 500) {
                    showError(errorText(response && response.message));
                    return;
                }
                applyResponse(state, response, page, config);
            }).catch(function () {
                showError('응답을 가져오지 못했습니다.');
            });
        }

        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                if (!input || input.disabled) return;
                const text = (input.value || '').trim();
                if (!text) return;
                input.value = '';
                if (sendBtn) sendBtn.disabled = true;
                sendChat(text, 'chat').then(function () {
                    renderLimit(state, config);
                    if (sendBtn && (Number(state.questionCount) || 0) < questionLimit(config)) {
                        sendBtn.disabled = false;
                    }
                    if (input && !input.disabled) input.focus();
                });
            });
        }
    }
})();
