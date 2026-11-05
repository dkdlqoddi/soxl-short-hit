import urllib.request

redirects = [
    ("11/4 코스피 마감 머니투데이", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqWCqvVg6DxdFaKpVHW2xzDuUTE4SuoFvqgaHecJS8dU4a09IDMMqgBYMDy6YA7SN4GEUq1HA7IbX3WWe3ZBDkc5Ds__MZd-Whr3OXm5Yung1cXx19yPugP44zw0ZBg5eql0JgxKtk2_lDSdpVGG4="),
    ("11/4 코스피 널뛰기 YTN", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGjHTie6McuwcxTwSAnhXeM710C9ewMJNEfDGdOx3Y75EtdMIOBsAhlb7cZefrI90hCKtoJk1G4RBs7YC6YdAzvFxL4EqF6tuKA_jodovwRDSi-B_wYqDLqGnqwZ5fqOLsgtWCVBO-S"),
    ("11/5 코스피 매도 사이드카 조선일보", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQERlOv9nvk3l4gnc3S_EmT0pV8uwZq-_igcjQcdELnySXIK2_579nfq6gPqFM9O2ec2IAyGE_c_1Oa178P6A14wzADBxNgp9PtZ9BfTXONCi3bppLACcJEguqkC4krYvIEPOeNRHRbxehpGQcTH424cZ67gbkGwr44CGKaVozcbY8I="),
    ("11/5 코스피 사이드카 연합뉴스", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEtV7rwtDRAtmysURglTqeN8a62I-4O1I5PWd4tbe_N_ojr6GtLFST1C0b8N57dNEz-NMRJUYUKzPuDHTGixNklWTDTxUfUqZkMSpEEp7rI6rSpAsITulfZOzs8hWTrYvmCkuKvVw=="),
    ("QCOM 실적 Motley Fool", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAVypGFVjwege7woNiVFDnqf75QcwGDF_xEZL7rMc3pY3hLzrX_SrCEgiqyxPgQaCNW_ZgcTht0f_PBgbMqUMyquZm_JW1yExqW4HXjvH4pYkYDXzIxpj-R-Ie1_f7inu5m9VQNSkVTBbibTE5HK1SO29hBcHNNZNt-YVFoy-PwPrSQD-mGdsCmrKFaHVzxoEsZ3eN33w4TY3SDAc="),
    ("ARM 실적 investingLive", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQECPUvPWzThEeowZcYglhQ0X7xENoecLnj48V33xT0p3wThFL27QGuCh9xtoJ7ZdD1s9CGxyQ8BS4QUvpG_cUYb9ymbIKmcBwk8R9WnckpLlzZt0rclburYwTT3Ty6CnpTsut4BMVEGtmg9BVqBlFaFM7xmz6dS_nv87fkJq4H0sEVRSYFHV7c1bsx0L-Ugc6dVaVZwQcVzHji56m0VSv2_9LwB4pOIUWybDg=="),
    ("미 중간선거 반도체 하락 Morningstar", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEZ42RWwAPv57p6ntZ6LxG6ueaSxzfp8D932v6SdaFVBXCrSHiA2zMlDjq0nEVjEzH_L4nhC9KRKq8uCJjPbi-iJ29YQMbM0YgD-337WVYCxaZ8bXLwF2Q06fZGzbSkq9axDMnWlz_fz9j0rqn13wJnxryhvYws1NtpypVheImpBNXfKgN3MN24Yzs62VLQlPvRtr24faut20In-vzKnc1FirUxAuznLqonu0llYv0yzRmfUydBl6kRn4c4sWMh86LOFyFmd06udnKtcS02gGQ="),
    ("ADP 10월 민간고용", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHZKkYDwWOelWSOrUnPR7ADcT0_S8cRo0ZGg-PQ8Rv4tfWwvXOxk6LpHKoXBtEIpyHp8N1YGO1_KlHwobfeRvTHw8AoyErwbEgfwRH4Esf09tX-kMOV94xC-jpl1PXxEPIgOb_9kJkewnyupMN3x4V6YndaQsTeg16AI9abWAnrh6-Bvmb_AJcfiP0LU-PMnFjxqtC3zN1J6dUa1FMsaeX-D6QW-zfed6awSqreVcfuFuAjtuXrlj_k7vk="),
    ("ISM 10월 서비스업 PMI PRNewswire", "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE6eVNNK2Fza5yFBkuz-oOW3wEi2nX913mHLiEi7MpEO36gWnozU9oXvXI-0DWhUuN1iWAN-RTV5-Rr8QmmFhW2edsb9tRhRPJRroJVOGp646FPPhpmUhYMa1Y4XRscMpkRx1nZy4dVMBoBteqS9E1By77HKModLUoCxdC0KGuJkNiZZbcSkvBkU5AZ_dUvHX53-I7-yEH8Yx9iKWAGGfHVWMHEn4Uupg=="),
]

headers = {"User-Agent": "Mozilla/5.0"}
for label, url in redirects:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            print(f"{label} -> {r.geturl()}")
    except Exception as e:
        print(f"{label} -> ERROR ({e})")
