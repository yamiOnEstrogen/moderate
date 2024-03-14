import argparse
import os
import time

import imageio
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

parser = argparse.ArgumentParser()

parser.add_argument(
    "--timeout", type=int, default=10, help="The time to wait for the page to load"
)
parser.add_argument(
    "--search", type=str, default=None, help="Search term to look for users"
)
parser.add_argument("--user", type=str, default=None, help="A user url to scrape from")

parser.add_argument(
    "--icapture",
    action="store_true",
    help="Capture the 3D Avatar on the user's profile",
)

parser.add_argument(
    "--capture-page", action="store_true", help="Screenshot the full user profile"
)

parser.add_argument(
    "--file",
    type=str,
    default=None,
    help="Import a members.txt file for processing. (https://github.com/0xYami/moderate/wiki/MembersFile)",
)

args = parser.parse_args()


def wait_and_get_element(driver, by, value, timeout=10):
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        print(f"Timeout waiting for element with {by}: {value}")
        return None


def click_element_safely(element):
    try:
        if element:
            element.click()
        else:
            print("Element is None. Cannot perform click.")
    except Exception as e:
        print(f"Error clicking element: {e}")


def get_counts(soup):
    counts = {}
    details_info = soup.find("ul", class_="details-info")

    if details_info:
        for li in details_info.find_all("li"):
            label = li.find("div", class_="text-label font-caption-header")
            count_element = li.find("span", class_="font-header-2")

            if label and count_element:
                count_type = label.text.strip()
                count_value = count_element["title"].strip()
                counts[count_type] = count_value

    return counts


def move_to_position(driver, web_element, up=0, down=0):
    driver.execute_script(
        "window.scrollTo(0, arguments[0].offsetTop - window.innerHeight / 2 + {} + {});".format(
            up, down
        ),
        web_element,
    )

    actions = ActionChains(driver)
    actions.move_to_element(web_element)
    actions.perform()


def capture_3d_avatar(driver, path):
    try:
        avatar_div = wait_and_get_element(
            driver, By.CSS_SELECTOR, ".col-sm-6.section-content.profile-avatar-left"
        )

        if avatar_div:
            move_to_position(driver, avatar_div, down=50)

            time.sleep(3)

            enable_3d_button = avatar_div.find_element(
                By.CSS_SELECTOR, ".enable-three-dee"
            )
            if "3D" in enable_3d_button.text:
                enable_3d_button.click()
                print("Switching to 3D...")

                time.sleep(3)
            else:
                print("Already in 3D mode.")

            screenshots = []
            start_time = time.time()
            while time.time() - start_time < 30:
                canvas_element = avatar_div.find_element(
                    By.CSS_SELECTOR, "canvas[data-engine='three.js r137']"
                )
                screenshot = canvas_element.screenshot_as_png
                screenshots.append(imageio.imread(screenshot))

                time.sleep(0.2)

            imageio.mimsave(
                os.path.join(path, "3d_avatar.gif"), screenshots, duration=0.2
            )
            print("3D avatar captured and saved as 3d_avatar_capture.gif")
            enable_3d_button.click()

    except Exception as e:
        print(f"Error capturing 3D avatar: {e}")


def download_avatar(avatar_url, directory):
    try:
        response = requests.get(avatar_url, stream=True)
        response.raise_for_status()

        with open(os.path.join(directory, "avatar.jpg"), "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print("Avatar downloaded and saved as avatar.jpg")
    except Exception as e:
        print(f"Error downloading avatar: {e}")


def capture_page(driver, path):
    try:
        body_element = wait_and_get_element(driver, By.TAG_NAME, "body")

        if body_element:
            element = body_element.find_element(By.CLASS_NAME, "container-main")
            if element:
                screenhot = element.screenshot_as_png
                imageio.imwrite(
                    os.path.join(path, "user_profile.png"), imageio.imread(screenhot)
                )
    except Exception as e:
        print(f"Error capturing page: {e}")


def scrape_details(driver, user_url, username, standalone=False):
    if not standalone:
        driver.execute_script("window.open();")
        driver.switch_to.window(driver.window_handles[1])

    directory = os.path.join(".", "found", "users", username)
    os.makedirs(directory, exist_ok=True)

    try:
        driver.get(user_url)

        wait_and_get_element(driver, By.TAG_NAME, "body")

        wait_and_get_element(driver, By.CLASS_NAME, "profile-name")

        soup = BeautifulSoup(driver.page_source, "html.parser")

        avatar_element_span = soup.find(
            "span", "thumbnail-2d-container avatar-card-image profile-avatar-thumb"
        )
        # favorites_button = wait_and_get_element(driver, By.CSS_SELECTOR, ".btn-more.see-all-link-icon[href*='/favorites#!/places']")

        if avatar_element_span:
            avatar_element = avatar_element_span.find("img")
            if avatar_element:
                avatar_url = avatar_element["src"]

        username_element = soup.find("h1", "profile-name text-overflow")
        display_name_element = soup.find(
            "div", "profile-display-name font-caption-body text text-overflow"
        )

        if username_element:
            username = username_element.text.strip()

        if display_name_element:
            display_name = display_name_element.text.strip()

        counts = get_counts(soup)

        file_path = os.path.join(directory, "details.txt")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"Name: {username}\n")
            file.write(f"Display Name: {display_name}\n")

            for count_type, count_value in counts.items():
                file.write(f"{count_type}: {count_value}\n")

        if avatar_url:
            download_avatar(avatar_url, directory)

        if args.icapture:
            capture_3d_avatar(driver, directory)

        if args.capture_page:
            capture_page(driver, directory)

    except Exception as e:
        print(f"Error loading or scraping page: {e}")
    finally:
        if not standalone:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])


def scrape_users(url="https://www.roblox.com/search/users"):
    driver = webdriver.Chrome()

    driver.get(url)
    driver.implicitly_wait(args.timeout or 10)

    if args.search:
        search_box = wait_and_get_element(driver, By.CLASS_NAME, "form-control")
        if search_box:
            search_box.send_keys(args.search)
            search_box.send_keys(Keys.RETURN)
            time.sleep(2)

            while True:
                soup = BeautifulSoup(driver.page_source, "html.parser")

                cards = soup.find_all("li", class_="player-item")

                if len(cards) == 0:
                    print("No users found on this page")
                    break

                for card in cards:
                    user_name = card.find(
                        "div",
                        class_="text-overflow avatar-card-label ng-binding ng-scope",
                    )
                    user_display_name = card.find(
                        "div", class_="text-overflow avatar-name ng-binding ng-scope"
                    )
                    user_link = card.find("a", "avatar-card-link")["href"]
                    print(
                        f"Getting data for {user_name.text} ({user_display_name.text}): {user_link}"
                    )
                    scrape_details(driver, user_link, user_name.text, False)
                    pass

                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

                new_soup = BeautifulSoup(driver.page_source, "html.parser")
                if new_soup == soup:
                    print("No more results. Exiting.")
                    break

                soup = new_soup
        else:
            print("Search box not found.")
    else:
        raise ValueError("Please enter a search term")
    pass


def main():
    if args.user is not None:
        driver = webdriver.Chrome()
        scrape_details(driver, args.user, True)
    elif args.file is not None:
        with open(args.file, "r") as file:
            lines = file.readlines()
            for line in lines:
                parts = line.split("(")
                username = parts[0].strip()
                url = parts[1].split(")")[0]

                driver = webdriver.Chrome()
                scrape_details(driver, url, username, True)
                driver.quit()
    else:
        scrape_users()


if __name__ == "__main__":
    main()
