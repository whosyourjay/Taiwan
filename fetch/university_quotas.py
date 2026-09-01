"""Download the ministry's per-department quota allocation, 表7-2."""

from fetch.high_school import download

QUOTAS = {
    "dir": "moe",
    "filename": "moe-115-quota.pdf",
    # ws.moe.edu.tw hands the file over only when both of its base64 parameters
    # match, so the display name has to travel with the path.
    "url": (
        "https://ws.moe.edu.tw/Download.ashx?u=LzAwMS9VcGxvYWQvNC9yZWxmaWxlLzc4"
        "NDAvMTAyNTUyL2NmMjg2YTI4LTU3MzEtNDc2ZC04NjQwLTBlNTcyMDNiMzJiMi5wZGY%3D"
        "&n=44CQ6KGoNy0y44CRMTE15a245bm05bqm5pel6ZaT5a245Yi25a245aOr54%2Bt5ZCE"
        "6Zmi57O757WE5a245L2N5a2456iL5paw55Sf5oub55Sf5ZCN6aGN5YiG6YWN6KGoLTEx"
        "NTA1MDUucGRm&icon=..pdf"
    ),
}


def main():
    download(QUOTAS, "moe")


if __name__ == "__main__":
    main()
