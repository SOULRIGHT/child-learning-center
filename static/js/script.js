// 지역아동센터 학습관리 시스템 - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // 페이지 로드 애니메이션
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        setTimeout(() => {
            card.classList.add('fade-in');
        }, index * 100);
    });

    // 점수 자동 계산 함수
    window.calculateScore = function(solvedInputId, correctInputId, scoreDisplayId) {
        const solvedInput = document.getElementById(solvedInputId);
        const correctInput = document.getElementById(correctInputId);
        const scoreDisplay = document.getElementById(scoreDisplayId);
        
        if (solvedInput && correctInput && scoreDisplay) {
            const solved = parseInt(solvedInput.value) || 0;
            const correct = parseInt(correctInput.value) || 0;
            
            // 맞은 문제가 푼 문제보다 많을 수 없음
            if (correct > solved) {
                correctInput.value = solved;
                return;
            }
            
            // 점수 계산 (맞은 문제 / 푼 문제 × 200점)
            const score = solved > 0 ? Math.round((correct / solved) * 200) : 0;
            scoreDisplay.textContent = score + '점';
        }
    };

    // 총점 계산 함수
    window.calculateTotalScore = function() {
        const koreanScore = parseInt(document.getElementById('korean-score')?.textContent) || 0;
        const mathScore = parseInt(document.getElementById('math-score')?.textContent) || 0;
        const readingScore = parseInt(document.getElementById('reading-score')?.textContent) || 0;
        
        const total = koreanScore + mathScore + readingScore;
        const totalDisplay = document.getElementById('total-score');
        if (totalDisplay) {
            totalDisplay.textContent = total + '점';
        }
        
        return total;
    };

    // 독서 완료 체크박스 처리
    window.toggleReading = function(checkboxId, scoreDisplayId) {
        const checkbox = document.getElementById(checkboxId);
        const scoreDisplay = document.getElementById(scoreDisplayId);
        
        if (checkbox && scoreDisplay) {
            scoreDisplay.textContent = checkbox.checked ? '200점' : '0점';
            calculateTotalScore();
        }
    };

    // 폼 유효성 검사
    window.validateForm = function(formId) {
        const form = document.getElementById(formId);
        if (!form) return false;
        
        let isValid = true;
        const requiredFields = form.querySelectorAll('[required]');
        
        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                field.classList.add('is-invalid');
                isValid = false;
            } else {
                field.classList.remove('is-invalid');
                field.classList.add('is-valid');
            }
        });
        
        return isValid;
    };

    // 숫자 입력 필드에 대한 유효성 검사
    const numberInputs = document.querySelectorAll('input[type="number"]');
    numberInputs.forEach(input => {
        input.addEventListener('input', function() {
            const value = parseInt(this.value);
            const min = parseInt(this.getAttribute('min')) || 0;
            const max = parseInt(this.getAttribute('max')) || 999;
            
            if (value < min) {
                this.value = min;
            } else if (value > max) {
                this.value = max;
            }
        });
    });

    // 검색 기능
    window.searchTable = function(inputId, tableId) {
        const input = document.getElementById(inputId);
        const table = document.getElementById(tableId);
        
        if (!input || !table) return;
        
        const filter = input.value.toLowerCase();
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
        
        for (let i = 0; i < rows.length; i++) {
            const cells = rows[i].getElementsByTagName('td');
            let found = false;
            
            for (let j = 0; j < cells.length; j++) {
                if (cells[j].textContent.toLowerCase().indexOf(filter) > -1) {
                    found = true;
                    break;
                }
            }
            
            rows[i].style.display = found ? '' : 'none';
        }
    };

    // 로딩 상태 표시
    window.showLoading = function(buttonId) {
        const button = document.getElementById(buttonId);
        if (button) {
            const originalText = button.innerHTML;
            button.innerHTML = '<span class="loading-spinner"></span> 처리중...';
            button.disabled = true;
            
            return function() {
                button.innerHTML = originalText;
                button.disabled = false;
            };
        }
    };

    // 날짜 포맷 함수
    window.formatDate = function(date) {
        const d = new Date(date);
        return d.getFullYear() + '-' + 
               String(d.getMonth() + 1).padStart(2, '0') + '-' + 
               String(d.getDate()).padStart(2, '0');
    };

    // 오늘 날짜를 기본값으로 설정
    const dateInputs = document.querySelectorAll('input[type="date"]');
    dateInputs.forEach(input => {
        if (!input.value) {
            input.value = formatDate(new Date());
        }
    });

    // 툴팁 초기화
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // 자동 저장 기능 (5분마다)
    window.autoSave = function() {
        const forms = document.querySelectorAll('form[data-autosave="true"]');
        forms.forEach(form => {
            const formData = new FormData(form);
            const data = {};
            for (let [key, value] of formData.entries()) {
                data[key] = value;
            }
            
            // localStorage에 임시 저장
            localStorage.setItem('autosave_' + form.id, JSON.stringify(data));
        });
    };

    // 자동 저장된 데이터 복원
    window.restoreAutoSave = function(formId) {
        const saved = localStorage.getItem('autosave_' + formId);
        if (saved) {
            const data = JSON.parse(saved);
            const form = document.getElementById(formId);
            
            if (form) {
                for (let [key, value] of Object.entries(data)) {
                    const input = form.querySelector(`[name="${key}"]`);
                    if (input) {
                        input.value = value;
                    }
                }
            }
        }
    };

    // 5분마다 자동 저장
    setInterval(autoSave, 5 * 60 * 1000);

    // 차트 생성 함수 (HTML/CSS 기반)
    window.createProgressChart = function(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container || !data) return;
        
        container.innerHTML = '';
        
        data.forEach(item => {
            const barContainer = document.createElement('div');
            barContainer.className = 'mb-3';
            
            const label = document.createElement('div');
            label.className = 'small text-muted mb-1';
            label.textContent = item.label;
            
            const progressBg = document.createElement('div');
            progressBg.className = 'progress';
            progressBg.style.height = '20px';
            
            const progressBar = document.createElement('div');
            progressBar.className = 'progress-bar';
            progressBar.style.width = item.percentage + '%';
            progressBar.textContent = item.value;
            
            progressBg.appendChild(progressBar);
            barContainer.appendChild(label);
            barContainer.appendChild(progressBg);
            container.appendChild(barContainer);
        });
    };

    // 성취도 차트 생성 함수
    window.createAchievementChart = function(containerId, data) {
        const container = document.getElementById(containerId);
        if (!container || !data) return;
        
        const maxValue = Math.max(...data.map(d => d.value));
        const chartHeight = 200;
        
        let chartHTML = '<div class="achievement-chart" style="height: ' + chartHeight + 'px; position: relative; border-bottom: 1px solid #ddd;">';
        
        data.forEach((item, index) => {
            const height = (item.value / maxValue) * (chartHeight - 40);
            const left = (index / (data.length - 1)) * 100;
            
            chartHTML += `
                <div class="chart-point" style="
                    position: absolute; 
                    left: ${left}%; 
                    bottom: ${height + 20}px;
                    width: 8px; 
                    height: 8px; 
                    background: #007bff; 
                    border-radius: 50%;
                    transform: translateX(-50%);
                "></div>
                <div class="chart-label" style="
                    position: absolute; 
                    left: ${left}%; 
                    bottom: 0;
                    transform: translateX(-50%);
                    font-size: 12px;
                    color: #666;
                ">${item.label}</div>
            `;
        });
        
        chartHTML += '</div>';
        container.innerHTML = chartHTML;
    };
});

// 전역 유틸리티 함수들
window.utils = {
    // API 호출 함수
    async fetchData(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            
            return await response.json();
        } catch (error) {
            console.error('Fetch error:', error);
            throw error;
        }
    },
    
    // 알림 표시
    showAlert(message, type = 'info') {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container, .container-fluid');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);
            
            // 5초 후 자동 제거
            setTimeout(() => {
                alertDiv.remove();
            }, 5000);
        }
    },
    
    // 확인 대화상자
    confirm(message, callback) {
        if (confirm(message)) {
            callback();
        }
    }
}; 