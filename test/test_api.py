import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. API 키 로드
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("❌ 오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    # 직접 입력해서 테스트하려면 아래 주석을 풀고 키를 넣으세요
    # api_key = "여기에_API_키_직접_입력" 
    exit()

print(f"🔑 API Key 확인됨: {api_key[:5]}..." + "*"*5)

# 2. 라이브러리 설정
try:
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"❌ 설정 오류: {e}")
    exit()

# 3. 사용 가능한 모델 목록 조회 (핵심!)
print("\n📋 [내 계정에서 사용 가능한 모델 목록]")
try:
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f" - {m.name}")
            available_models.append(m.name)
            
    if not available_models:
        print("⚠️ 사용 가능한 모델이 하나도 없습니다. API 키 권한이나 지역 제한을 확인하세요.")
        exit()
        
except Exception as e:
    print(f"❌ 모델 목록 조회 실패: {e}")
    print("팁: 'pip install --upgrade google-generativeai' 로 라이브러리를 업데이트 해보세요.")
    exit()

# 4. 연결 테스트 (최신 모델 우선 시도)
print("\n🚀 [연결 테스트 시작]")

# 테스트할 모델 후보군
test_candidates = ['models/gemini-1.5-flash', 'models/gemini-pro', 'models/gemini-1.0-pro']

# 목록에 있는 것 중 하나로 테스트
target_model = None
for candidate in test_candidates:
    if candidate in available_models:
        target_model = candidate
        break

if not target_model:
    # 목록에 없어도 강제 시도 (가끔 목록엔 안떠도 될 때가 있음)
    target_model = 'gemini-1.5-flash' 

print(f"👉 테스트 대상 모델: {target_model}")

try:
    model = genai.GenerativeModel(target_model)
    response = model.generate_content("안녕? 너는 누구니? 짧게 대답해줘.")
    
    print("\n✅ [테스트 성공!]")
    print(f"🤖 AI 응답: {response.text}")
    print("-" * 30)
    print(f"이제 코드에서 model_name = '{target_model}' (또는 'models/' 제외한 이름) 을 사용하시면 됩니다.")

except Exception as e:
    print(f"\n❌ [테스트 실패]")
    print(f"에러 내용: {e}")