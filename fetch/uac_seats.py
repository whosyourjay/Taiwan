"""Download UAC's post-return 分發入學 seat table."""

from fetch.high_school import download


SEATS = {
    "dir": "uac",
    "filename": "115-count.xlsx",
    "url": "https://www2.uac.edu.tw/uac115_note/count.xlsx",
}


def main():
    download(SEATS, "uac")


if __name__ == "__main__":
    main()
