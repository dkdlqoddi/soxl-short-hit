#!/usr/bin/env python3
import json
import urllib.request

OUT_DIR = "/home/dkdlqoddi/012_gemini/soxl-short-hit/research/2026-11-06/koru-data/argon"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

urls_to_resolve = {
    "yna_cb": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGNUnmScPz_EmJpD1WBUZamcLOdH8fst7s4RmQrLPrpDDy3GRytSEVv1U3Y53a8j7YIMc745gpWEidR2fhOFGzp4EZTTsuYtp17Z2nn3GQIeZARffHjWeN2u0siADsiQzx_eGYBYw==",
    "newsis_f4": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEnm12965xb7etSuJ443-kdNbs2bKzJGZOgUagjAXHFFEx8QF_TV4lNeMhrSelfDCJCfD9MbhuIedEIYhrzLkK7Qi5MG3eAlwbMbIZAenug_6rZs1oX3kiU3e0qg4AqQSqQSkYhXrFvH73nar0=",
    "sbs_f4": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFtYumOsI9UcSEmTFW5GKO5FuD5ZD5uG2ApPeM2kZ4G2ehvZ9hE8BP21qfz0q1l1RcfKAJ1vmoZ_Ycr3y6yzHwg2Uo1b7NXATjHFo19VwA1qxswmBQvn71W6tvgiugJbA==",
    "forbes_datacenter": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEGyBdOT58BEl3VzfPrqv7DOil7AV4eRWGXsoF9fFwOsnBuqRqaXHRyeoh_h5_d51knvMchR27mqwP2MZPdXSo8jcYI69YWhhnSJZ_meRgm5V8IFIGekL54qTSdkL5NN2D3uC-pYe-kGR0xUPzjpii099N0gyh0aso92h2j2W3SbDZqS27dyk6LLwPaJsqTM0xha6Rqz4Xc3OkQASGGNBvUW9n9CuthRHpakLSmYZOJ77dezFISY1qXi9XIkSo=",
    "investing_nfp": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFlGDcQcDqKlsKclowR-4wVdkmO3_eegvqE2YgS7E9q37W__UBacU1aXK5VmmY1UGEY0n60FcsWCOQw2oWEDLwkOtzX1p2uIuAOs6mLODBtci5vnPg_9AQQjnQYidErANPgeIB9MZoKyQhM6Rmubz-C8BWUKkYp-b1fhfJvhDAebZywQusM_e8yCnN5F19uyXl5KmTYiyXWVisUVAwnIACD2jFlKjoclnLaV_MjbzTwU2rCk4N1pM993rtiDPk=",
    "investing_cal": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH7NfdVywEqBTsF0mNSH6R1VmYEgsqMAro0EonTrRq_fRPTsmA2XkleV3BahBGCKu1IUetLT-Z687ZrCCrtcs0bAT85GGAlEYBrmnE6uGTJ0DyeHOUk1QPozUcShLAwQ0sgL0kr5o5SwEgqFyK_I09gyh0_gBunS6Gh5RF-LNW1k9rMTK5-EpAzao1E87vNfe8fz2uM85rt4OkzliljeCHodX27E8izi8VNwiCCpoePzRhRu0Mul-oQI0Sl2aI=",
    "umich": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEAsADCN0A8amX2NQjdeU2863gyc1RJNtOtpZt2q23vCjJIATlgY2sFKfLVWcd41CrOThouNVHMXkbhFZO6tkfAgk2rf4MHWoaPzhEj91GAYL_OnAg=",
}

resolved = {}
for k, u in urls_to_resolve.items():
    try:
        req = urllib.request.Request(u, headers=HEADERS, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as r:
            resolved[k] = r.geturl()
    except Exception:
        try:
            req = urllib.request.Request(u, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as r:
                resolved[k] = r.geturl()
        except Exception as e:
            resolved[k] = f"ERR: {e}"

with open(f"{OUT_DIR}/forecast_resolved_urls.json", "w", encoding="utf-8") as f:
    json.dump(resolved, f, ensure_ascii=False, indent=2)
print(json.dumps(resolved, ensure_ascii=False, indent=2))
