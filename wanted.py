from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
import sqlite3
import time

def create_url(category : list):
    """
    category 번호를 받아서 url 반환하는 함수

    Note:
    파이썬개발자 : selected=899
    데이터엔지니어 : selected=655
    빅데이터엔지니어 : selected=1025
    머신러닝엔지니어 :selected=1634
    데이터사이언티스트 : selected=1024
    영상음성엔지니어 : selected=896
    """
    category_url = ""
    for temp_category in category:
        category_url += f"selected={temp_category}&"
    url = f"https://www.wanted.co.kr/wdlist/518?country=kr&job_sort=company.response_rate_order&years=0&years=2&{category_url}locations=all"
    return url

def init_database():
    """
    데이터베이스 초기화

    urlinfo 테이블 
    : 크롤링 중 오류가 날 수 있기 때문에 URL 정보를 우선 적재합니다.
    
    JDinfo 테이블 
    : 각 JD의주요 업무, 요구 사항, 우대 사항, 혜택 및 복지, 기술스택 ・ 툴을 적재합니다.
    """
    timeinfo = int(time.time())
    conn = sqlite3.connect(f'wanted_{timeinfo}.db')
    cur = conn.cursor()
    SQL_CTEATE_URL_INFO_TABLE = """
    CREATE TABLE IF NOT EXISTS urlinfo (
        url TEXT PRIMARY KEY NOT NULL,
        title VARCHAR(32),
        company VARCHAR(16)
    );
    """
    cur.execute(SQL_CTEATE_URL_INFO_TABLE)

    SQL_CTEATE_JD_INFO_TABLE = """
    CREATE TABLE IF NOT EXISTS JDinfo (
        JD_id INTEGER PRIMARY KEY AUTOINCREMENT,
        JobToDo TEXT,
        requirement TEXT,
        preferential TEXT,
        welfare TEXT,
        skills TEXT,
        close_date TEXT,
        location TEXT,
        url TEXT,
        --
        FOREIGN KEY (url) REFERENCES urlinfo(url)
    );
    """
    cur.execute(SQL_CTEATE_JD_INFO_TABLE)
    cur.close()
    conn.close()
    print("init database를 성공했습니다.")
    return timeinfo

def get_conn_cur(timeinfo: int):
    conn = sqlite3.connect(f'wanted_{timeinfo}.db')
    cur = conn.cursor()
    return conn, cur

def scroll_down(driver):
    """
    스크롤 끝까지 내리는 코드
    """
    SCROLL_PAUSE_SEC = 3
    # 스크롤 높이 가져옴
    last_height = driver.execute_script("return document.body.scrollHeight")
    while True:
        # 끝까지 스크롤 다운
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        # 1초 대기
        time.sleep(SCROLL_PAUSE_SEC)
        # 스크롤 다운 후 스크롤 높이 다시 가져옴
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    print("스크롤 다운 완료!")

def url_crawler(driver, category_num_list: list):
    timeinfo = init_database()
    URL = create_url(category_num_list)

    driver.get(URL)

    scroll_down(driver)

    ### 공고 URL 모으는 코드 ###
    elems = driver.find_elements(By.CLASS_NAME, 'Card_className__u5rsb')
    conn, cur = get_conn_cur(timeinfo)
    URL_list = []
    for elem in elems:
        ### url, 공고 제목, 회사 데이터 수집 ###
        temp_card = elem.find_element(By.TAG_NAME, 'a')
        temp_text = temp_card.text
        temp_list = temp_text.split('\n')
        temp_url = temp_card.get_attribute('href')

        URL_list.append(temp_url)
        SQL_INSERT_URLINFO = f"INSERT INTO urlinfo (url, title, company) VALUES ('{temp_url}', '{temp_list[0]}', '{temp_list[1]}')"

        cur.execute(SQL_INSERT_URLINFO)
    conn.commit()
    cur.close()
    conn.close()
    return timeinfo

def jd_info_crawler(driver, timeinfo, sleep_time):
    """
    내용 크롤링 함수
    """
    conn, cur = get_conn_cur(timeinfo)
    SQL = """
        SELECT u.url
        FROM urlinfo AS u
        LEFT JOIN JDinfo AS j
        ON u.url=j.url
        WHERE j.url IS NULL
        """
    cur.execute(SQL)
    URL_list = [x[0] for x in cur.fetchall()]
    for URL in URL_list:
        driver.get(URL)
        time.sleep(sleep_time)
        try:
            cont = driver.find_element(By.CLASS_NAME, 'JobDescription_JobDescription__VWfcb')
            contents_header = cont.find_elements(By.TAG_NAME, 'h6')
            preferential = ""
            skills = ""
            for header in contents_header:
                ### 주요업무, 자격요건, 우대사항, 혜택 및 복지, 기술스택&툴 데이터 수집 ###
                temp_contents = header.find_element(By.XPATH, 'following-sibling::*')
                if header.text == "주요업무":
                    JobToDo = temp_contents.text
                    JobToDo = JobToDo.replace("'", '"')
                elif header.text == "자격요건":
                    requirement = temp_contents.text
                    requirement = requirement.replace("'", '"')
                elif header.text == "우대사항":
                    preferential = temp_contents.text
                    preferential = preferential.replace("'", '"')
                elif header.text == "혜택 및 복지":
                    welfare = temp_contents.text
                    welfare = welfare.replace("'", '"')
                elif header.text == "기술스택 ・ 툴":
                    skills = temp_contents.text
                    skills = skills.replace("'", '"')
            ### 마감일, 근무지역 데이터를 위해 특정 부분까지 스크롤 다운 ###
            action = ActionChains(driver)
            cont = driver.find_element(By.CLASS_NAME, 'StealingWarning_StealingWarning_content__Ik3sn')
            action.move_to_element(cont).perform()
            time.sleep(sleep_time-1)
            parents_object = driver.find_element(By.CLASS_NAME, 'JobWorkPlace_className__ra6rp')
            text = parents_object.text
            text_split = text.split('\n')
            close_date = text_split[0].lstrip('마감일')
            location = text_split[1].lstrip('근무지역')

            SQL_INSERT_JDINFO = f"""
            INSERT INTO JDinfo (JobToDo, requirement, preferential, welfare, skills, close_date, location, url) 
            VALUES ('{JobToDo}', '{requirement}', '{preferential}', '{welfare}', '{skills}', '{close_date}', '{location}', '{URL}')
            """
            cur.execute(SQL_INSERT_JDINFO)
            conn.commit()
        except:
            print("채용 정보를 가져오지 못 했습니다.")
            continue
    cur.close()
    conn.close()

def check_if_failed(timeinfo):
    conn, cur = get_conn_cur(timeinfo)
    SQL = """
        SELECT u.url
        FROM urlinfo AS u
        LEFT JOIN JDinfo AS j
        ON u.url=j.url
        WHERE j.url IS NULL
        """
    cur.execute(SQL)
    result = cur.fetchall()
    cur.close()
    conn.close()
    if result:
        return True
    return False

def crawling_until_end(driver, timeinfo, sleep_time):
    CHECK = check_if_failed(timeinfo)
    SLEEP_TIME = sleep_time
    if CHECK:
        SLEEP_TIME += 1
        jd_info_crawler(driver, timeinfo, SLEEP_TIME)
        crawling_until_end(driver, timeinfo, SLEEP_TIME)

if __name__=="__main__":
    from webdriver_manager.chrome import ChromeDriverManager

    driver = webdriver.Chrome(ChromeDriverManager().install())

    ### 원하는 카테고리 번호 & 첫 시도 sleep 초 입력 ###
    CATEGORY_NUM_LIST = [899, 655, 1025]
    SLEEP_TIME = 1

    timeinfo = url_crawler(driver, CATEGORY_NUM_LIST)
    jd_info_crawler(driver, timeinfo, SLEEP_TIME)
    crawling_until_end(driver, timeinfo, SLEEP_TIME)
    print("크롤링 끄-읕!")