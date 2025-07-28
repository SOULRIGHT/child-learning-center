// 독서 상태 선택 함수 (별도 파일)
function selectReadingStatus(button, status) {
    console.log('함수 호출됨:', status);
    
    // 모든 버튼 초기화
    var buttons = document.querySelectorAll('.reading-status-btn');
    for (var i = 0; i < buttons.length; i++) {
        var btn = buttons[i];
        btn.classList.remove('btn-success', 'btn-warning', 'btn-secondary', 'active');
        btn.classList.remove('btn-outline-success', 'btn-outline-warning', 'btn-outline-secondary');
        
        var btnValue = btn.getAttribute('data-value');
        if (btnValue === 'complete') {
            btn.classList.add('btn-outline-success');
        } else if (btnValue === 'partial') {
            btn.classList.add('btn-outline-warning');
        } else if (btnValue === 'none') {
            btn.classList.add('btn-outline-secondary');
        }
    }
    
    // 선택된 버튼 활성화
    button.classList.remove('btn-outline-success', 'btn-outline-warning', 'btn-outline-secondary');
    button.classList.add('active');
    
    var score = 0;
    var completed = false;
    
    if (status === 'complete') {
        button.classList.add('btn-success');
        score = 200;
        completed = true;
    } else if (status === 'partial') {
        button.classList.add('btn-warning');
        score = 100;
        completed = false;
    } else if (status === 'none') {
        button.classList.add('btn-secondary');
        score = 0;
        completed = false;
    }
    
    // hidden input 업데이트
    document.getElementById('reading_status').value = status;
    document.getElementById('reading_score').value = score;
    document.getElementById('reading_completed').value = completed;
    
    // 독서 점수 즉시 반영
    var readingElement = document.getElementById('reading_contribution');
    if (readingElement) {
        readingElement.textContent = score.toFixed(1) + '점';
        console.log('독서 점수 업데이트 성공:', score);
    } else {
        console.error('reading_contribution 요소를 찾을 수 없습니다!');
    }
    
    // 직접 총점 계산 및 UI 업데이트
    updateTotalScore();
    console.log('총점 계산 완료');
    
    console.log('독서 점수 업데이트 완료:', score);
}

// 총점 계산 및 UI 업데이트 함수
function updateTotalScore() {
    // 국어 점수 계산
    var koreanSolved = parseInt(document.getElementById('korean_problems_solved').value) || 0;
    var koreanCorrect = parseInt(document.getElementById('korean_problems_correct').value) || 0;
    var koreanScore = calculateScore(koreanCorrect, koreanSolved);
    
    // 수학 점수 계산
    var mathSolved = parseInt(document.getElementById('math_problems_solved').value) || 0;
    var mathCorrect = parseInt(document.getElementById('math_problems_correct').value) || 0;
    var mathScore = calculateScore(mathCorrect, mathSolved);
    
    // 독서 점수
    var readingScore = parseFloat(document.getElementById('reading_score').value) || 0;
    
    // 총점 계산
    var totalScore = koreanScore + mathScore + readingScore;
    
    // UI 업데이트
    document.getElementById('korean_contribution').textContent = koreanScore.toFixed(1) + '점';
    document.getElementById('math_contribution').textContent = mathScore.toFixed(1) + '점';
    document.getElementById('reading_contribution').textContent = readingScore.toFixed(1) + '점';
    document.getElementById('total_score_preview').textContent = totalScore.toFixed(1) + '점';
    
    // 진행률 바 업데이트
    var progressElement = document.getElementById('total_progress');
    var progressWidth = Math.min((totalScore / 4), 100) + '%';
    progressElement.style.width = progressWidth;
    
    // 등급 표시
    var ratingElement = document.getElementById('score_rating');
    if (totalScore >= 370) {
        ratingElement.textContent = '우수';
        ratingElement.className = 'badge bg-success fs-6';
        progressElement.className = 'progress-bar bg-success';
    } else if (totalScore >= 320) {
        ratingElement.textContent = '양호';
        ratingElement.className = 'badge bg-primary fs-6';
        progressElement.className = 'progress-bar bg-primary';
    } else if (totalScore >= 250) {
        ratingElement.textContent = '보통';
        ratingElement.className = 'badge bg-warning fs-6';
        progressElement.className = 'progress-bar bg-warning';
    } else if (totalScore > 0) {
        ratingElement.textContent = '미흡';
        ratingElement.className = 'badge bg-danger fs-6';
        progressElement.className = 'progress-bar bg-danger';
    } else {
        ratingElement.textContent = '점수를 입력해주세요';
        ratingElement.className = 'badge bg-secondary fs-6';
        progressElement.className = 'progress-bar bg-secondary';
    }
    
    console.log('총점 업데이트:', totalScore);
}

// 점수 계산 함수 (복사)
function calculateScore(correct, total) {
    if (total === 0 || correct === 0) return 0;
    return (correct / total) * 100;
} 