import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = "https://lk.yandexdataschool.ru"
LOGIN_URL = BASE_URL + "/login/"
COURSE_URL = BASE_URL + "/courses/2024-autumn/7.1277-random-processes/"
CLASSES_URL = COURSE_URL + "classes/"
ASSIGNMENTS_URL = COURSE_URL + "assignments/"

USERNAME = ""
PASSWORD = ""

session = requests.Session()
headers = {
    "User-Agent": "Mozilla/5.0",
}

# === Получаем CSRF-токен ===
login_page = session.get(LOGIN_URL, headers=headers)
soup = BeautifulSoup(login_page.text, "html.parser")
csrf = soup.find("input", {"name": "csrfmiddlewaretoken"}).get("value")

# === Логинимся ===
login_data = {
    "username": USERNAME,
    "password": PASSWORD,
    "csrfmiddlewaretoken": csrf,
}
response = session.post(
    LOGIN_URL, data=login_data, headers={**headers, "Referer": LOGIN_URL}
)

# === Проверка входа ===
if "Войдите на сайт" in response.text or response.url.endswith("/login/"):
    print("❌ Логин не удался. Проверь логин/пароль.")
    exit()

print("✅ Успешный вход!")


# === Функция парсинга занятий курса ===
def parse_course_classes(session: requests.Session, course_classes_url: str) -> dict:
    response = session.get(course_classes_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Название курса
    title_elem = soup.select_one("h2.course-main-title")
    course_name = (
        title_elem.contents[0].strip()
        if title_elem
        else "Unknown course" if title_elem else "Unknown course"
    )

    rows = soup.find("div", id="course-classes").select("table")[0].find_all("tr")

    classes = []

    for row in rows[1:]:
        tds = row.find_all("td")
        if len(tds) < 2:
            continue

        # Безопасно получаем ссылку на занятие
        link_tag = tds[1].find("a")
        if not link_tag or not link_tag.get("href"):
            continue

        class_url = urljoin(BASE_URL, link_tag["href"])
        class_name = link_tag.get_text(strip=True)

        print(f"📄 Обработка занятия: {class_name}")

        # Загружаем страницу занятия
        class_resp = session.get(class_url)
        class_resp.raise_for_status()
        class_soup = BeautifulSoup(class_resp.text, "html.parser")

        video_url = None
        video_heading = class_soup.find(
            "h4", string=lambda t: t and "Ссылка на запись" in t
        )
        if video_heading:
            video_link = video_heading.find_parent("a", href=True)
            if video_link:
                video_url = video_link["href"]

        # Ищем вложения (файлы)
        attachments = []
        attachment_list = class_soup.find("ul", class_="list")
        if attachment_list:
            for a in attachment_list.select("a[href^='/attachments/']"):
                file_name = a.get_text(strip=True)
                file_url = urljoin(BASE_URL, a["href"])
                attachments.append({"name": file_name, "url": file_url})

        # === Добавляем занятие в список
        classes.append(
            {
                "title": class_name,
                "url": class_url,
                "video": video_url,
                "attachments": attachments,
            }
        )

    return {"course_name": course_name, "classes": classes}


def save_course_to_disk(course_data: dict, base_dir="courses"):
    course_name = course_data["course_name"]
    classes = course_data["classes"]

    # Путь к корневой папке курса
    course_folder = os.path.join(base_dir, course_name)
    os.makedirs(course_folder, exist_ok=True)

    for idx, cls in enumerate(classes):
        class_folder_name = cls["title"].replace("/", "_").replace(":", "_")
        class_folder = os.path.join(
            course_folder, f"Занятие {idx + 1}: {class_folder_name}"
        )
        os.makedirs(class_folder, exist_ok=True)

        # README.md с ссылкой на видео
        readme_path = os.path.join(class_folder, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {cls['title']}\n\n")
            f.write(f"**Ссылка на занятие:** [{cls['url']}]({cls['url']})\n\n")
            if cls["video"]:
                f.write(f"📺 [Смотреть запись]({cls['video']})\n\n")
            else:
                f.write("❌ Запись не найдена\n\n")

        # Скачивание вложений
        for file in cls["attachments"]:
            filename = file["name"].replace("/", "_")
            filepath = os.path.join(class_folder, filename)

            print(f"⬇️ Скачивание {filename}...")
            try:
                resp = session.get(file["url"])
                resp.raise_for_status()
                with open(filepath, "wb") as out_file:
                    out_file.write(resp.content)
            except Exception as e:
                print(f"⚠️ Не удалось скачать {filename}: {e}")

    print(f"\n✅ Курс сохранён в папке: {course_folder}")


def parse_course_assignments(session: requests.Session, assignments_url: str) -> dict:
    response = session.get(assignments_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    title_elem = soup.select_one("h2.course-main-title")
    course_name = title_elem.contents[0].strip() if title_elem else "Unknown course"

    assignments = []
    for block in (
        soup.find("div", id="course-assignments").select("table")[0].find_all("tr")[1:]
    ):
        tds = block.find_all("td")
        if len(tds) < 2:
            continue

        link_tag = tds[1].find("a")
        if not link_tag:
            continue

        assignment_title = link_tag.get_text(strip=True)
        assignment_url = urljoin(BASE_URL, link_tag["href"])

        assignment_resp = session.get(assignment_url)
        assignment_resp.raise_for_status()
        assignment_soup = BeautifulSoup(assignment_resp.text, "html.parser")

        # Парсим файлы на странице ДЗ
        attachments = []
        for a in assignment_soup.select(
            "a[href^='/learning/attachments/assignments/']"
        ):
            file_name = a.get_text(strip=True)
            file_url = urljoin(BASE_URL, a["href"])
            attachments.append({"name": file_name, "url": file_url})

        assignments.append(
            {
                "title": assignment_title,
                "url": assignment_url,
                "attachments": attachments,
            }
        )

    return {"course_name": course_name, "assignments": assignments}


# === Сохранение домашних заданий ===
def save_assignments_to_disk(data: dict, base_dir="courses"):
    course_name = data["course_name"]
    assignments = data["assignments"]

    base_path = os.path.join(base_dir, course_name, "Домашние задания")
    os.makedirs(base_path, exist_ok=True)

    for idx, a in enumerate(assignments):
        folder_name = a["title"].replace("/", "_").replace(":", "_")
        folder_path = os.path.join(base_path, f"ДЗ {idx + 1}: {folder_name}")
        os.makedirs(folder_path, exist_ok=True)

        readme_path = os.path.join(folder_path, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(f"# {a['title']}\n\n")
            f.write(f"**Ссылка на задание:** [{a['url']}]({a['url']})\n\n")

        for file in a["attachments"]:
            filename = file["name"].replace("/", "_")
            filepath = os.path.join(folder_path, filename)
            print(f"⬇️ Скачивание {filename}...")
            try:
                resp = session.get(file["url"])
                resp.raise_for_status()
                with open(filepath, "wb") as out_file:
                    out_file.write(resp.content)
            except Exception as e:
                print(f"⚠️ Не удалось скачать {filename}: {e}")

    print(f"\n✅ Домашки сохранены в папке: {base_path}")


course_data = parse_course_classes(session, CLASSES_URL)
save_course_to_disk(course_data)

assignments_data = parse_course_assignments(session, ASSIGNMENTS_URL)
save_assignments_to_disk(assignments_data)
