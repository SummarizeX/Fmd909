# app.py
from flask import Flask, request, jsonify
import langid
import asyncio
import re

app = Flask(__name__)
# context = ssl.SSLContext()
# context.load_cert_chain('cert.pem', 'key.pem')
from urllib.parse import urlparse
import re
import requests
from settings import get_choere_key

import cohere
from dbm_api import dbm_get_reviews, dbm_put_reviews

# import openai


asin_reg = "(?:[/dp/]|$)([A-Z0-9]{10})"
REVIEWS_MAX_PAGES = 1
MAX_TOKENS_RESPONSE = 6000
MAX_WORDS_IN_PROMPT = 800
MAX_WORDS_IN_ARABIC_PROMPT = 500

client = cohere.Client(get_choere_key())


def fix_request_before_handling(request):
    if 'force_review_request' not in request:
        request['force_review_request'] = False


@app.route("/")
def hello_world():
    print("received / request")

    return "<p>Hello, World! - SummarizeX</p>"


@app.route("/summarize", methods=['POST'])
def summarize():
    print("received summarize request")

    url = request.json['url']
    fix_request_before_handling(request.json)

    res = summarize_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['summary'] = res['summary'] if code == 200 else res['error_msg']
    return res, code


@app.route("/summarize_ex", methods=['POST'])
def summarize_ex():
    print("received summarize_ex request")

    url = request.json['url']
    fix_request_before_handling(request.json)

    res = summarize_ex_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['summary'] = res['summary'] if code == 200 else res['error_msg']
    return res, code


@app.route("/generative_summary", methods=['POST'])
def generative_summary():
    print("received generative_summary request")

    url = request.json['url']
    fix_request_before_handling(request.json)

    res = generate_summary_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    return res, code


# @app.route("/summarize_WhatsApp", methods=['POST'])
# def summarize_ex():
#     url = request.json['url']
#     fix_request_before_handling(request.json)
#
#     res = summarize_ex_handler(request.json)
#     res['url'] = url
#     code = res['error'] if 'error' in res else 200
#     res['summary'] = res['summary'] if code == 200 else res['error_msg']
#     return res, code

@app.route("/summarize_WhatsApp", methods=['POST'])
def summarize_whatsapp():
    url = request.json['url']
    fix_request_before_handling(request.json)

    res = summarize_ex_handler2(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['summary'] = res['summary'] if code == 200 else res['error_msg']
    messages = {'messages': res}
    return messages


@app.route("/summarize_BulletPoints", methods=['POST'])
def summarize_summarize_bulletPoints():
    url = request.json['url']
    fix_request_before_handling(request.json)

    res = summarize_ex_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['summary'] = res['summary'] if code == 200 else res['error_msg']
    messages = {'text': res['summary']}
    return messages


@app.route("/query_ex", methods=['POST'])
def generative_query_ex():
    print("received query request")
    url = request.json['url']

    fix_request_before_handling(request.json)

    res = answer_query_ex_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['answer'] = res['answer'] if code == 200 else res['error_msg']

    return res, code


# expects 'url' and 'query'
@app.route("/query", methods=['POST'])
def generative_query():
    print("received query request")
    url = request.json['url']

    fix_request_before_handling(request.json)

    res = answer_query_handler(request.json)
    res['url'] = url
    code = res['error'] if 'error' in res else 200
    res['answer'] = res['answer'] if code == 200 else res['error_msg']

    return res, code


def answer_query_ex_handler(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)
    domain = res['domain']
    asin = res['asin']

    print("asin = ", asin)
    reviews, votes = dbm_get_reviews(asin)

    if reviews == None or request['force_review_request'] == True:
        reviews, votes = reviews_api_wrapper(domain, asin)

    response = client.rerank(
        model='rerank-english-v2.0',
        query=request['query'],
        documents=reviews,
        top_n=20,
    )
    print("ranked res ", response[:5])
    lang = 'Arabic' if ('language' in request and request['language'] == 'ar') else 'English'
    lang_max = MAX_WORDS_IN_PROMPT if lang == 'English' else MAX_WORDS_IN_ARABIC_PROMPT
    used_reviews = []
    sz = 0
    for r in response.results:
        i = r.index
        used_reviews.append(reviews[i])
        sz += len(reviews[i])

        if sz > MAX_WORDS_IN_PROMPT:
            break

    text = "\n".join(used_reviews)
    prompt_en = f"This program answers the question {request['query']} in depth based on information in the following sentences" \
                f"{text}" \
                f"Respond in {lang}. the answer to the question {request['query']} is: "

    prompt_ar = "هذا البرنامج يجاوب على السؤال التالي {query} بناءا على هذه المعلومات:" \
                f"{text}" \
                "الجواب هو:"
    prompt = prompt_en if lang == 'english' else prompt_ar

    # response = openai.Completion.create(
    #     model="text-davinci-003",
    #     prompt=prompt,
    #     temperature=0.2,
    #     max_tokens=1028,
    #     top_p=1,
    #     frequency_penalty=0,
    #     presence_penalty=0
    # )

    res['answer'] = response['choices'][0]['text']
    print("answer :", res['answer'])
    return res


def answer_query_handler(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)
    domain = res['domain']
    asin = res['asin']

    print("asin = ", asin)
    reviews, votes = dbm_get_reviews(asin)
    print("reviews = ", reviews)

    if reviews == None or request['force_review_request'] == True:
        reviews, votes = reviews_api_wrapper(domain, asin)

    response = client.rerank(
        model='rerank-english-v2.0',
        query=request['query'],
        documents=reviews,
        top_n=20,
    )
    print("ranked res ", response)

    used_reviews = []
    sz = 0
    for r in response.results:
        i = r.index
        used_reviews.append(reviews[i])
        sz += len(reviews[i])

        if sz > MAX_WORDS_IN_PROMPT:
            break
    text = "\n".join(used_reviews)
    lang = 'Arabic' if 'sa' in domain else 'English'
    prompt = f"This program answers the question {request['query']} in depth based on information in the following sentences" \
             f"{text}" \
             f"Respond in {lang}. the answer to the question {request['query']} is: "

    # response = openai.Completion.create(
    #     model="text-davinci-003",
    #     prompt=prompt,
    #     temperature=0.2,
    #     max_tokens=1028,
    #     top_p=1,
    #     frequency_penalty=0,
    #     presence_penalty=0
    # )

    res['answer'] = response['choices'][0]['text']
    print("answer :", res['answer'])
    return res


def get_domain_and_asin(url, res):
    # check if its coming from amazon
    domain = urlparse(url).netloc
    if "amazon" not in domain:
        res['error'] = 500
        res['error_msg'] = "Sorry currently we support only Amazon"
        return res

    first = domain.find("amazon")
    domain = domain[first:]
    # extracting asin
    # https://www.amazon.com/Lasko-U35115-Electric-Oscillating-Velocity/dp/B081HDGZML?ref_=Oct_DLandingS_D_e95f1a2b_2&th=1
    # m = re.match(asin_reg, url)
    m = re.search(r'/[dg]p/([^/]+)', url, flags=re.IGNORECASE)
    word = m.group(1)
    if word is not None:
        if word[0] == '/':
            asin = word[1:11]
        else:
            asin = word[:10]
    else:
        res['error'] = 404
        res['error_msg'] = "ASIN could not be extracted"
        return res

    print(f"found asin {asin} and domain {domain}")
    res['asin'] = asin
    res['domain'] = domain


def summarize_ex_handler(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)

    if 'error' in res.keys():
        return res

    domain = res['domain']
    asin = res['asin']

    reviews, votes = dbm_get_reviews(asin)

    # call reviews api
    if 'language' in request and request['language'] == 'ar':
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin, options={'language': 'ar_SA'})

        # res['summary'] = openAI_arabic(reviews)
    else:
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin)

        res['summary'] = run_cohere_summarization(reviews)
        del res['domain']
        del res['asin']

        summaryBulletPoints = run_cohere_summarizationBulletPoints(reviews)

        pros = []
        cons = []
        proscounter = 1
        conscounter = 1
        sentences = []
        sentences.extend(summaryBulletPoints.split('\n'))
        for sentence in sentences:
            if "+ " in sentence:
                pros.append(sentence.replace("+ ", str(proscounter) + '-'))
                proscounter += 1
            elif "- " in sentence:
                cons.append(sentence.replace("- ", str(conscounter) + '-'))
                conscounter += 1

    res['pros'] = pros
    res['cons'] = cons

    return res


def summarize_ex_handler2(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)

    if 'error' in res.keys():
        return res

    domain = res['domain']
    asin = res['asin']

    reviews, votes = dbm_get_reviews(asin)

    # call reviews api
    if 'language' in request and request['language'] == 'ar':
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin, options={'language': 'ar_SA'})

        # res['summary'] = openAI_arabic(reviews)
    else:
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin)

        res['summary'] = run_cohere_summarization(reviews)

        del res['domain']
        del res['asin']

        summaryBulletPoints = run_cohere_summarizationBulletPoints(reviews)

        pros = []
        cons = []
        proscounter = 1
        conscounter = 1
        sentences = []
        sentences.extend(summaryBulletPoints.split('\n'))
        for sentence in sentences:
            if "+ " in sentence:
                if proscounter < 6:
                    pros.append(sentence.replace("+ ", str(proscounter) + '-'))
                    proscounter += 1
            elif "- " in sentence:
                if conscounter < 6:
                    cons.append(sentence.replace("- ", str(conscounter) + '-'))
                    conscounter += 1

    pros_string = '  '.join(pros)
    cons_string = '  '.join(cons)

    res['pros'] = pros_string
    res['cons'] = cons_string

    return res



def summarize_ex_get_handler(request):
    url = request['url']
    res = {}
    domain = urlparse(url).netloc
    if "amazon" not in domain:
        res['error_msg'] = "Sorry currently we support Amazon only"
        return res

    first = domain.find("amazon")
    domain = domain[first:]
    # extracting asin
    # https://www.amazon.com/Lasko-U35115-Electric-Oscillating-Velocity/dp/B081HDGZML?ref_=Oct_DLandingS_D_e95f1a2b_2&th=1
    # m = re.match(asin_reg, url)
    m = re.search(r'/[dg]p/([^/]+)', url, flags=re.IGNORECASE)
    word = m.group(1)
    if word is not None:
        if word[0] == '/':
            asin = word[1:11]
        else:
            asin = word[:10]
    else:
        res['error'] = 404
        res['error_msg'] = "ASIN could not be extracted"
        return res

    if 'error' in res.keys():
        return res

    domain = res['domain']
    asin = res['asin']

    reviews, votes = dbm_get_reviews(asin)

    # call reviews api
    if 'language' in request and request['language'] == 'ar':
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin, options={'language': 'ar_SA'})

        # res['summary'] = openAI_arabic(reviews)
    else:
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin)

        res['summary'] = run_cohere_summarization(reviews)
        del res['domain']
        del res['asin']

        summaryBulletPoints = run_cohere_summarizationBulletPoints(reviews)

        pros = []
        cons = []
        sentences = []
        sentences.extend(summaryBulletPoints.split('\n'))
        for sentence in sentences:
            if "+ " in sentence:
                pros.append(sentence.replace("+ ", ""))
            elif "- " in sentence:
                cons.append(sentence.replace("- ", ""))

    res['pros'] = pros
    res['cons'] = cons

    return res


def summarize_handler(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)

    if 'error' in res.keys():
        return res

    domain = res['domain']
    asin = res['asin']

    reviews, votes = dbm_get_reviews(asin)

    # call reviews api
    if '.sa' in domain:
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin, options={'language': 'ar_SA'})

        # res['summary'] = openAI_arabic(reviews)
    else:
        if reviews == None or request['force_review_request'] == True:
            reviews, votes = reviews_api_wrapper(domain, asin)

        res['summary'] = run_cohere_summarization(reviews)
    print("output: ", res['summary'])
    dbm_put_reviews(asin, reviews, votes)

    return res


def run_cohere_summarization(reviews):
    text = "\n".join(reviews)
    summary = client.summarize(text,
                               additional_command="summarize customer opinions and generate a single paragraph describing overall customer sentiment towards the product")
    return summary.summary


def run_cohere_summarizationBulletPoints(reviews):
    text = "\n".join(reviews)

    summary = client.summarize(text,
                               additional_command="Show as bullet points indicating the positive aspects of the product with a '+' symbol and the negative aspects of the product with a '-' symbol")

    return summary.summary


def run_cohere_generative_summary(reviews):
    text = ""
    sz = 0
    for r in reviews:
        if sz + len(r) < MAX_WORDS_IN_PROMPT:
            text += "\n" + r
            sz += len(r)

    prompt = f"Each new line contains a product review from a customer. At the end a summary of the overall sentiment towards the product, the main advantages and disadvantages of the product, the main qualitative descriptors used for the product, will be written:" \
             f"{text}  " \
             f" In summary: "
    summary = client.generate(prompt, max_tokens=MAX_TOKENS_RESPONSE, temperature=0.3)
    return summary.generations[-1].text


def reviews_api_wrapper(domain, asin, num_pages=1, options={}):
    params = {
        'api_key': 'E736023FED8A4A3AADD2C5F549932C7A',
        'amazon_domain': domain,
        'asin': asin,
        'type': 'reviews',
        'output': 'json',
        'page': 1,
        **options
    }

    total_reviews = []
    total_votes = []

    for i in range(1, num_pages + 1):
        params['page'] = i
        print("params = ", params)

        # make the http GET request to ASIN Data API
        api_result = requests.get('https://api.rainforestapi.com/request', params)
        res_json = api_result.json()
        # print(res_json)
        # print("----------------------------------------------------")
        # extract reviews only
        reviews = []
        helpful_votes = []
        # for x in res_json['reviews']:
        #     reviews.append(x['body'])
        #     if 'helpful_votes' in x.keys():
        #         helpful_votes.append(x['helpful_votes'])
        #     else:
        #         helpful_votes.append(0)
        #
        # total_reviews.extend(reviews)
        # total_votes.extend(helpful_votes)

        for x in res_json['reviews']:
            if 'body' in x:
                # Check if the review is in English
                if langid.classify(x['body'])[0] == 'en':
                    # Check if the review contains text (not just images)
                    if re.sub(r'<img[^>]+>', '', x['body']).strip():
                        reviews.append(x['body'])
                        if 'helpful_votes' in x.keys():
                            helpful_votes.append(x['helpful_votes'])
                        else:
                            helpful_votes.append(0)

        total_reviews.extend(reviews)
        total_votes.extend(helpful_votes)

        total_pages = res_json['pagination']['total_pages']

        if i == total_pages:
            break
    print(f"returned a total of {len(total_reviews)} reviews")
    return total_reviews, total_votes


# def openAI_arabic(reviews) :
#
#     text = ""
#     sz = 0
#     for r in reviews:
#         if sz + len(r) < MAX_WORDS_IN_ARABIC_PROMPT:
#             text += "\n" + r
#             sz += len(r)
#
#     prompt = "لخصل المراجعات التالية واذكر الانطباع العام تجاه المنتج و ايجابياته و سلبياته" \
#     f"{text}" \
#     "الملخص: "
#
#     # print("openAI prompt: ", prompt)
#     # response = openai.Completion.create(
#     #     model="text-davinci-003",
#     #     prompt=prompt,
#     #     temperature=0.2,
#     #     max_tokens=700,
#     #     top_p=1,
#     #     frequency_penalty=0,
#     #     presence_penalty=0
#     # )
#
#     return response['choices'][0]['text']

def generate_summary_handler(request):
    url = request['url']
    res = {}
    get_domain_and_asin(url, res)

    if 'error' in res.keys():
        return res

    domain = res['domain']
    asin = res['asin']

    reviews, votes = dbm_get_reviews(asin)

    if '.sa' in res['domain']:
        if reviews == None:
            reviews, votes = reviews_api_wrapper(domain, asin, options={'language': 'ar_SA'})
        else:
            print("using cache")
    else:
        if reviews == None:
            reviews, votes = reviews_api_wrapper(domain, asin)

        res['generative'] = run_cohere_generative_summary(reviews)

    print("output: ", res['generative'])
    dbm_put_reviews(asin, reviews, votes)
    return res


# def test_sum():
#     url = 'https://www.amazon.com/Lasko-U35115-Electric-Oscillating-Velocity/dp/B081HDGZML?ref_=Oct_DLandingS_D_e95f1a2b_2&th=1'
#     res = summarize_handler(url)
#     print(res)
#     print(res.decode("hex").decode("utf8"))


if __name__ == "__main__":
    # app.run(ssl_context=context)
    app.run()
    # test_sum()
