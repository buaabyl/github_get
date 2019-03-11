# github get

You will find this table when opened a github page.

![How it works](how_it_works.png)

This script using pycurl and BeautifulSoup4.

- pycurl: download page from github
- bs4: analysis html, and extract table
- lxml: bs4 backend

How to use

```sh
github_get.py https://github.com/Xilinx/linux-xlnx/tree/master/drivers/net/can
```

you will find `cache` and `download` directories.

