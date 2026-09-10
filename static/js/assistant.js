(function () {
    const STORAGE_KEY = 'clc.teacherAssistant.v1';
    const STAGE_EL = '[data-assistant-role="character-stage"]';

    function boot() {
        const node = document.getElementById('assistant-page-context');
        if (!node) return null;
        try {
            return JSON.parse(node.textContent);
        } catch (err) {
            return null;
        }
    }

    function emptyState() {
        return {
            version: 1,
            drawerOpen: false,
            childId: null,
            generalMessages: [],
            childMessages: [],
        };
    }

    function loadState() {
        try {
            const raw = sessionStorage.getItem(STORAGE_KEY);
            if (!raw) return emptyState();
            const parsed = JSON.parse(raw);
            if (!parsed || parsed.version !== 1) return emptyState();
            return {
                version: 1,
                drawerOpen: Boolean(parsed.drawerOpen),
                childId: parsed.childId == null ? null : parsed.childId,
                generalMessages: Array.isArray(parsed.generalMessages) ? parsed.generalMessages : [],
                childMessages: Array.isArray(parsed.childMessages) ? parsed.childMessages : [],
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
                generalMessages: (state.generalMessages || []).slice(-20),
                childMessages: (state.childMessages || []).slice(-20),
            }));
        } catch (err) {
            return;
        }
    }

    function isolateChild(state, page) {
        const nextId = page && page.child_id != null ? page.child_id : null;
        if (state.childId !== nextId) {
            state.childMessages = [];
            state.childId = nextId;
        }
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
            context_scope: message.context_scope || {},
            actions: message.actions || [],
        };
        if (isChildScoped(copy)) {
            state.childMessages.push(copy);
        } else {
            state.generalMessages.push(copy);
        }
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
        if (!node) return;
        if (!text) {
            node.hidden = true;
            node.textContent = '';
            return;
        }
        node.hidden = false;
        node.textContent = text;
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
                    if (!action || !action.url) return;
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'assistant-action';
                    btn.textContent = action.label || '열기';
                    btn.setAttribute('data-assistant-nav', action.url);
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

    function applyResponse(state, payload, page) {
        if (!payload || !payload.message) return;
        const message = payload.message;
        message.actions = payload.actions || [];
        storeMessage(state, message);
        saveState(state);
        renderMessages(state);
        renderOnboarding(payload.status);
        renderQuick(payload.quick_actions, visibleMessages(state).length > 0);
        setStage(payload.character_state || 'idle');
        showError('');
        const auto = (payload.actions || []).find(function (action) {
            return action && action.auto && action.url;
        });
        if (auto && auto.url) {
            window.location.assign(auto.url);
        }
    }

    function post(config, body) {
        return fetch(config.message_url, {
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
        let state = isolateChild(loadState(), page);
        saveState(state);
        renderMessages(state);
        renderQuick(null, visibleMessages(state).length > 0);
        setStage('idle');

        const launcherEl = document.getElementById('teacherAssistantLauncher');
        const offcanvas = bootstrap.Offcanvas.getOrCreateInstance(drawer);
        if (state.drawerOpen) {
            if (launcherEl) launcherEl.hidden = true;
            offcanvas.show();
        }

        drawer.addEventListener('shown.bs.offcanvas', function () {
            state.drawerOpen = true;
            saveState(state);
            if (launcherEl) launcherEl.hidden = true;
            post(config, {
                intent: 'bootstrap',
                messages: [],
                page_context: page,
            }).then(function (payload) {
                if (payload._httpStatus >= 500) {
                    showError(payload.message || '조교 응답을 가져오지 못했습니다.');
                    return;
                }
                renderOnboarding(payload.status);
                const hasTranscript = visibleMessages(state).length > 0;
                renderQuick(payload.quick_actions, hasTranscript);
                const root = qs('conversation');
                if (root && !hasTranscript && !root.childNodes.length && payload.message) {
                    const intro = document.createElement('div');
                    intro.className = 'assistant-bubble is-assistant';
                    intro.textContent = payload.message.content || '무엇을 도와드릴까요?';
                    root.appendChild(intro);
                }
            }).catch(function () {
                showError('조교 응답을 가져오지 못했습니다. 기존 화면은 그대로 사용할 수 있어요.');
            });
        });

        drawer.addEventListener('hidden.bs.offcanvas', function () {
            state.drawerOpen = false;
            saveState(state);
            if (launcherEl) launcherEl.hidden = false;
        });

        drawer.addEventListener('click', function (event) {
            const nav = event.target.closest('[data-assistant-nav]');
            if (nav) {
                const url = nav.getAttribute('data-assistant-nav');
                if (url) window.location.assign(url);
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
            const payload = {
                intent: action.intent || 'chat',
                destination: action.destination || null,
                params: action.params || {},
                messages: visibleMessages(state).concat([{
                    role: 'user',
                    content: action.label || action.intent || '',
                    context_scope: { endpoint: page.endpoint || '', child_id: page.child_id || null },
                }]),
                page_context: page,
            };
            storeMessage(state, payload.messages[payload.messages.length - 1]);
            saveState(state);
            renderMessages(state);
            renderQuick(null, true);
            setStage('thinking');
            post(config, payload).then(function (response) {
                if (response._httpStatus >= 500 || response.ok === false && !response.message) {
                    showError((response && response.message) || '조교 응답을 가져오지 못했습니다.');
                    return;
                }
                applyResponse(state, response, page);
            }).catch(function () {
                showError('조교 응답을 가져오지 못했습니다. 기존 화면은 그대로 사용할 수 있어요.');
            });
        }

        if (form) {
            form.addEventListener('submit', function (event) {
                event.preventDefault();
                if (!input) return;
                const text = (input.value || '').trim();
                if (!text) return;
                input.value = '';
                if (sendBtn) sendBtn.disabled = true;
                const userMessage = {
                    role: 'user',
                    content: text,
                    context_scope: { endpoint: page.endpoint || '', child_id: page.child_id || null },
                };
                storeMessage(state, userMessage);
                saveState(state);
                renderMessages(state);
                renderQuick(null, true);
                setStage('thinking');
                post(config, {
                    intent: 'chat',
                    messages: visibleMessages(state),
                    page_context: page,
                }).then(function (response) {
                    if (response._httpStatus >= 500) {
                        showError((response && response.message) || '조교 응답을 가져오지 못했습니다.');
                        return;
                    }
                    applyResponse(state, response, page);
                }).catch(function () {
                    showError('조교 응답을 가져오지 못했습니다. 기존 화면은 그대로 사용할 수 있어요.');
                }).then(function () {
                    if (sendBtn) sendBtn.disabled = false;
                    if (input) input.focus();
                });
            });
        }
    }
})();
