import os
os.chdir('C:/Users/서시현/Desktop/etc/website/music_web')

import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver

def save_melon_to_csv():
    # 1. 설정 정보 (분석 시 필터링을 위해 년도 정보를 변수로 관리)
    target_decade = "2020년대"
    target_year = "2025년"
    target_url = "https://www.melon.com/chart/age/index.htm?chartType=YE&chartGenre=KPOP&chartDate=2025#params%5Bidx%5D=1"
    
    print(f"{target_year} 차트 수집을 시작합니다...")
    
    # --- [Step 1] 곡 링크 수집 (이전과 동일) ---
    driver = webdriver.Chrome()
    driver.get(target_url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    detail_buttons = soup.select("a.btn_icon_detail")
    
    song_urls = [f"https://www.melon.com{btn.get('href')}" for btn in detail_buttons if "songId=" in btn.get('href')]
    driver.quit()

    # --- [Step 2] 상세 정보 수집 및 리스트에 저장 ---
    results = [] # 데이터를 담을 바구니
    headers = {"User-Agent": "Mozilla/5.0 ..."} # 실제 브라우저 헤더 입력

    for url in song_urls[-50:]:
        try:
            response = requests.get(url, headers=headers)
            detail_soup = BeautifulSoup(response.text, 'html.parser')
            
            title = detail_soup.select_one(".song_name").text.replace("곡명", "").strip()
            artist = detail_soup.select_one(".artist a").text.strip()
            lyric_element = detail_soup.select_one("#d_video_summary")
            lyrics = lyric_element.get_text(separator=' ').strip() if lyric_element else ""

            # 분석을 위해 딕셔너리 형태로 데이터를 쌓습니다.
            results.append({
                "decade": target_decade,
                "year": target_year,
                "title": title,
                "artist": artist,
                "lyrics": lyrics,
                "url": url
            })
            print(f"수집 완료: {title}")
            time.sleep(1.2)
        except Exception as e:
            print(f"오류 발생: {e}")

    # --- [Step 3] 데이터프레임 변환 및 저장 ---
    df = pd.DataFrame(results)
    
    # CSV로 저장 (encoding='utf-8-sig'는 엑셀에서 한글 깨짐을 방지합니다)
    file_name = f"melon_{target_year}_data.csv"
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    
    print("\n" + "="*30)
    print(f"파일 저장 완료: {file_name}")
    print(f"수집된 데이터 개수: {len(df)}개")
    print("="*30)

if __name__ == "__main__":
    save_melon_to_csv()

# ☆ 파일 가져오기 ☆
# import glob # 파일 전체 가져오기, 이름 뒤에 * 붙여서 한번에 가져오기 꿀팁
# import pandas as pd
# stations_files = glob.glob('./지역_위치별(주유소)*xls')


# ★ 전처리만 잘하면 함수대입 그냥 됨(train, test 동일한 전처리 해야함에 주의) ★
# ☆ 결측값 대체 ☆
# import seaborn as sns
#     df = sns.load_dataset('titanic')
# X = df[['age', 'fare']] #변수가 하나라고 대괄호([])를 하나만 적으면 series형태임
# from sklearn.impute import SimpleImputer # or KNNImputer
# si = SimpleImputer(strategy = 'mean') # missing_values = , #지정값을 결측값으로 생각하도록 함.
# si.fit(X) # 값이 si에 저장됨 (train만 넣어줌)
# si.transform(X) # 값을 X에 넣어줌
# #=> 출력형태 : 2d array => 데이터프레임 형태로 변환해야함.
# import pandas as pd
# X1 = pd.DataFrame(si.transform(X), columns=X.columns)

# ☆ 표준화 ☆ # 대부분의 경우 y는 안함
# from sklearn.preprocessing import StandardScaler
# ss = StandardScaler()
# ss.fit(X_train_re[['age', 'fare']]) #re sampling한 결과가 더 좋게 나옴으로
# X_train_re[['age', 'fare']] = pd.DataFrame(ss.transform(X_train_re[['age', 'fare']]))

# ☆ 인코딩 ☆
# from sklearn.preprocessing import LabelEncoder
# le = LabelEncoder()

# # 혹은 더미변수
# import pandas as pd
# X = pd.get_dummies(X, columns=['class'], drop_first = True, dtype='int')# int 중요

# ☆ 그 외 ☆
# pd.concat([ df1, df2 ] )

# pd.merge(df1, df2, left_on= right_on = , how = left right inner outer)

# stations.rename(columns = {'상호':'Oil_store', '휘발유':'가격', '셀프여부':'셀프'}, inplace = True)

# df = df.replace(0, np.nan).dropna()

# df.sort_values(by = ['연', '월'], ascending = True)

# d1 = df1.groupby(['수송일자', '호선', '역명']).sum()
# d1.reset_index(inplace=True) # 중요

# df_grouped = df_reset.groupby('연')[['월', '금리']].sum()
# df_grouped = df_grouped.reset_index()  # 인덱스를 컬럼으로 풀기

# ★ 함수대입 -> 결과도출 (파라미터 튜닝 x, default만 ) rf, gb, xgb, lgbm ★
# ☆ R F ☆
# from sklearn.ensemble import RandomForestClassifier

# ☆ G B ☆
# from sklearn.ensemble import GradientBoostingClassifier

# ☆ X G B ☆
# from xgboost import XGBClassifier

# ☆ L G B M☆
# from lightgbm import LGBMClassifier

# - Logistic Regression
# from sklearn.linear_model import LogisticRegression

# ★ 결론도출
# from sklearn.metrics import classification_report
# print(classification_report(y_test, pred_2))  

# from sklearn.metrics import f1_score
# f1_score(y_test, y_test_pred, average=None)

# from sklearn.metrics import confusion_matrix
# confusion_matrix(y_test, pred_2)

# from sklearn.metrics import recall_score
# recall_score(y_test, pred_2, average=None)



import os
os.chdir('C:/Users/서시현/Desktop/etc/website/music_web')

import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver

def save_melon_to_csv():
    # 1. 설정 정보
    target_decade = "2020년대"
    target_year = "2025년"
    target_url = "https://www.melon.com/chart/age/index.htm?chartType=YE&chartGenre=KPOP&chartDate=2025#params%5Bidx%5D=1"
    
    print(f"{target_year} 차트 수집을 시작합니다...")
    
    # --- [Step 1] 곡 링크 수집 (수정된 부분) ---
    driver = webdriver.Chrome()
    driver.get(target_url)
    time.sleep(3)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    
    # 중복을 방지하기 위해 각 순위별 행(tr)에서 고유한 곡 ID(data-song-no)를 직접 추출합니다.
    song_trs = soup.select("tbody > tr")
    song_urls = []
    
    for tr in song_trs:
        song_id = tr.get("data-song-no")
        if song_id:
            song_urls.append(f"https://www.melon.com/song/detail.htm?songId={song_id}")
            
    # 정확히 상위 50개만 추출하고 싶다면 아래와 같이 리스트를 자릅니다.
    song_urls = song_urls[-50:] 
    
    driver.quit()

    # --- [Step 2] 상세 정보 수집 및 리스트에 저장 ---
    results = [] 
    # 웹페이지 접근 거부를 방지하기 위해 실제 브라우저 헤더를 풀버전으로 작성합니다.
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    } 

    # [Step 1]에서 이미 50개로 잘라두었으므로, 여기서는 그대로 순회합니다.
    for rank, url in enumerate(song_urls, start=1):
        try:
            response = requests.get(url, headers=headers)
            detail_soup = BeautifulSoup(response.text, 'html.parser')
            
            # NoneType 에러 방지를 위해 요소 추출을 조금 더 안전하게 수정
            title_elem = detail_soup.select_one(".song_name")
            title = title_elem.text.replace("곡명", "").strip() if title_elem else "알 수 없음"
            
            artist_elem = detail_soup.select_one(".artist a")
            artist = artist_elem.text.strip() if artist_elem else "알 수 없음"
            
            lyric_element = detail_soup.select_one("#d_video_summary")
            lyrics = lyric_element.get_text(separator=' ').strip() if lyric_element else ""

            results.append({
                "decade": target_decade,
                "year": target_year,
                "rank": rank, # 데이터 확인을 편하게 하기 위해 순위(rank)도 추가했습니다.
                "title": title,
                "artist": artist,
                "lyrics": lyrics,
                "url": url
            })
            print(f"[{rank}위] 수집 완료: {title}")
            time.sleep(1.2)
        except Exception as e:
            print(f"오류 발생 ({url}): {e}")

    # --- [Step 3] 데이터프레임 변환 및 저장 ---
    df = pd.DataFrame(results)
    
    file_name = f"melon_{target_year}_data.csv"
    df.to_csv(file_name, index=False, encoding='utf-8-sig')
    
    print("\n" + "="*30)
    print(f"파일 저장 완료: {file_name}")
    print(f"수집된 데이터 개수: {len(df)}개")
    print("="*30)

if __name__ == "__main__":
    save_melon_to_csv()