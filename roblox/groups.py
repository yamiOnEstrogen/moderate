import argparse
import os
import time

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
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
    "--search", type=str, default=None, help="Search term to look for groups"
)
parser.add_argument(
    "--pages", type=int, default=1, help="Maximum number of pages to scrape"
)
parser.add_argument("--gurl", type=str, default=None, help="A group URL")

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


def scrape_group_details(driver, group_url, standalone=False):
    group_id = group_url.split("/")[-2]

    directory = os.path.join(".", "found", "groups", group_id)
    os.makedirs(directory, exist_ok=True)

    if not standalone:
        driver.execute_script("window.open();")
        driver.switch_to.window(driver.window_handles[-1])

    try:
        driver.get(group_url)
        driver.implicitly_wait(args.timeout or 10)
        body_element = driver.find_element("tag name", "body")
        description = ""
        soup = BeautifulSoup(driver.page_source, "html.parser")

        description_element = soup.find(
            "div", class_="group-description toggle-target ng-scope"
        )
        name_element = soup.find("h1", class_="group-name text-overflow ng-binding")

        if description_element:
            read_more_link = description_element.find(
                "span", class_="toggle-content text-link cursor-pointer ng-binding"
            )
            if read_more_link:
                if callable(getattr(read_more_link, "click", None)):
                    read_more_link.click()
                    time.sleep(2)

        description = (
            description_element.text.strip()
            if description_element
            else "No description available"
        )

        file_path = os.path.join(directory, "group_details.txt")
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"Group URL: {group_url}\n")
            file.write(f"Group Description: {description}\n")

        members_file_path = os.path.join(directory, "members.txt")
        for _ in range(5):
            body_element.send_keys(Keys.PAGE_DOWN)
            time.sleep(0)
        with open(members_file_path, "w", encoding="utf-8") as members_file:
            while True:
                try:
                    members_elem = driver.find_elements(
                        By.CSS_SELECTOR, ".list-item.member"
                    )
                    for member in members_elem:
                        name_element = member.find_element(
                            By.CSS_SELECTOR, ".member-name.ng-binding"
                        )
                        link_element = member.find_element(By.XPATH, ".//a[@ng-href]")
                        if link_element:
                            link = link_element.get_attribute("ng-href")
                            if link:
                                members_file.write(
                                    f"Username: {name_element.text.strip()}\n"
                                )
                            members_file.write(f"Link: {link}\n")

                    has_exp = driver.find_elements(By.TAG_NAME, "group-games")

                    if has_exp:
                        next_button = driver.find_elements(
                            By.CLASS_NAME, "btn-generic-right-sm"
                        )[1]
                    else:
                        next_button = driver.find_elements(
                            By.CLASS_NAME, "btn-generic-right-sm"
                        )[0]

                    is_disabled = driver.execute_script(
                        "return arguments[0].disabled", next_button
                    )
                    if not is_disabled:
                        move_to_position(driver, next_button)
                        next_button.click()
                        time.sleep(1)
                    else:
                        print("Member Searching done!")
                        break

                except NoSuchElementException as e:
                    print(f"Error finding element: {e}")
                    break
                except Exception as e:
                    print(f"Error during member scraping: {e}")
                    break

    except Exception as e:
        print(f"Error during group details scraping: {e}")

    finally:
        if not standalone:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])


def scrape_groups(url="https://www.roblox.com/search/groups"):
    driver = webdriver.Chrome()

    driver.get(url)
    driver.implicitly_wait(args.timeout or 10)

    if args.search:
        search_box = driver.find_element(By.ID, "GroupSearchField")
        search_box.send_keys(args.search)
        search_box.send_keys(Keys.RETURN)
        time.sleep(2)

        for page in range(args.pages):
            print(f"Processing Page {page + 1}")

            body_element = driver.find_element("tag name", "body")
            for _ in range(9):
                body_element.send_keys(Keys.PAGE_DOWN)
                time.sleep(0.5)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            group_cards = soup.find_all("li", class_="list-item")

            if len(group_cards) == 0:
                print("No groups found on this page")
                break

            for group_card in group_cards:
                group_name = group_card.find(
                    "div", class_="font-header-2 text-overflow ng-binding"
                ).text

                group_url = group_card.find("a", class_="group-search-name-link")[
                    "href"
                ]

                access_element = group_card.find("div", class_="group-card-access")
                access_status = access_element.text.strip() if access_element else ""

                if "Private" in access_status:
                    print(f"Group {group_name} is private. Skipping...")
                    continue

                print("Group %s: %s is being processed" % (group_name, group_url))
                scrape_group_details(driver, group_url)

            next_button = driver.find_element(By.CLASS_NAME, "btn-generic-right-sm")
            if next_button.is_enabled():
                move_to_position(driver, next_button)
                time.sleep(0.5)
                next_button.click()
                time.sleep(2)
            else:
                print("No more pages to process")
                break
    else:
        body_element = driver.find_element("tag name", "body")
        for _ in range(9):
            body_element.send_keys(Keys.PAGE_DOWN)
            time.sleep(0.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        group_cards = soup.find_all(
            "group-card", class_="game-card ng-scope ng-isolate-scope"
        )

        if len(group_cards) == 0:
            print("No groups found")
            driver.quit()
            return

        for group_card in group_cards:
            group_name = group_card.find("div", class_="game-card-name").text
            group_url = group_card.find("a")["href"]
            print("Group %s: %s is being processed" % (group_name, group_url))
            scrape_group_details(driver, group_url)

    if args.autoclose:
        driver.quit()
        return


def main():
    if args.gurl is not None:
        driver = webdriver.Chrome()
        scrape_group_details(driver, args.gurl, True)
    else:
        scrape_groups()


if __name__ == "__main__":
    main()
