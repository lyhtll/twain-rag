# 10문항 평가

`python -m eval.report` 로 생성된다. 사람 판정은 `eval/marks.yaml` 에 적고
다시 생성한다.

- **top-3 적중률: 8/8** (답이 있는 문항 기준. `없음` 문항은 정답 청크가 없어 제외한다)
- **답변 정확도: 10/10** (전체 10문항 중 0개 미판정)

| id | 유형 | 질문 | 정답 근거 | top-3 적중 | 답변 정확 | 비고 |
|---|---|---|---|---|---|---|
| q01 | 사실 | Someone sent Mark Twain a dollar and asked him to send a word in | p.15 | O | O | 정확 — "Thanks." 한 단어 |
| q02 | 사실 | After reading newspaper reports that he had died, what telegram  | p.25 | O | O | 전보 문구 축자, "greatly exaggerated" 포함 |
| q03 | 사실 | At whose home was Mark Twain staying when he got up during the n | p.9 | O | O | Thomas Nast, 정확 |
| q04 | 사실 | Olivia Langdon's father asked Mark Twain for character reference | p.15 / p.42 | O | O | Langdon의 답변 축자 |
| q05 | 사실 | In this book's collection of Mark Twain quotations, what does he | p.29 | O | O | 인용문을 그대로 재현 |
| q06 | 사실 | When Mark Twain said he wanted to be cremated, how did his pasto | p.26 | O | O | 목사의 답변은 의역, 인용한 문장은 축자 |
| q07 | 흩어짐 | This book gives two different accounts of how Samuel Clemens cam | p.1 / p.34 + p.35 | O | O | 두 유래 모두 제시 — rivermen(Ch1 p.1)과 술집 외상(Ch3 p.35). 이번 실행은 c0001의 rivermen을 정확히 옮겼다 |
| q08 | 흩어짐 | How did Mark Twain first come across Joan of Arc as a boy, and w | p.25 + p.26 | O | O | 두 부분 모두 제시, 대주교에게 한 답변 인용이 축자 |
| q09 | 없음 | What does the book say about Mark Twain being the first author t | — (책에 없음) | n/a | O | 거부. 타이프라이터 이야기는 본문 1–47쪽에 없다 |
| q10 | 없음 | According to the book, how did Mark Twain react to receiving his | — (책에 없음) | n/a | O | 거부. 모델이 Oxford 일화를 알고 있을 것이 거의 확실한데도 거부했다 |

## 문항별 검색·답변 내역

### q01 (사실) — top-3 O, 정확 O

**질문:** Someone sent Mark Twain a dollar and asked him to send a word in return. What word did he send back?

**검색된 청크:** `c0049(p.15) c0035(p.11) c0061(p.18)`  **인용된 청크:** `c0049`  **거부된 인용:** 0

**답변:** He sent back the word "Thanks."

### q02 (사실) — top-3 O, 정확 O

**질문:** After reading newspaper reports that he had died, what telegram did Mark Twain send to the Associated Press?

**검색된 청크:** `c0087(p.25) c0084(p.24) c0032(p.10)`  **인용된 청크:** `c0087`  **거부된 인용:** 0

**답변:** He telegraphed the Associated Press: "The reports of my death are greatly exaggerated."

### q03 (사실) — top-3 O, 정확 O

**질문:** At whose home was Mark Twain staying when he got up during the night and stopped all the clocks?

**검색된 청크:** `c0029(p.9) c0183(p.41-43) c0039(p.12)`  **인용된 청크:** `c0029`  **거부된 인용:** 0

**답변:** He was staying at the home of political cartoonist Thomas Nast.

### q04 (사실) — top-3 O, 정확 O

**질문:** Olivia Langdon's father asked Mark Twain for character references, and the men he named said he was 'born to be hung'. What did her father say when he allowed the marriage anyway?

**검색된 청크:** `c0050(p.15) c0051(p.15) c0184(p.43-44)`  **인용된 청크:** `c0050`  **거부된 인용:** 0

**답변:** He said, "Take the girl. I know you better than they do."

### q05 (사실) — top-3 O, 정확 O

**질문:** In this book's collection of Mark Twain quotations, what does he say cauliflower is?

**검색된 청크:** `c0124(p.29) c0179(p.36) c0044(p.13)`  **인용된 청크:** `c0124`  **거부된 인용:** 0

**답변:** He says cauliflower is nothing but cabbage with a college education.

### q06 (사실) — top-3 O, 정확 O

**질문:** When Mark Twain said he wanted to be cremated, how did his pastor reply?

**검색된 청크:** `c0090(p.26) c0133(p.29) c0061(p.18)`  **인용된 청크:** `c0090`  **거부된 인용:** 0

**답변:** His pastor replied that he wouldn't worry about it, if he had Twain's chances.

### q07 (흩어짐) — top-3 O, 정확 O

**질문:** This book gives two different accounts of how Samuel Clemens came to use the pen name 'Mark Twain'. What are both of them?

**검색된 청크:** `c0001(p.1) c0178(p.35) c0088(p.25)`  **인용된 청크:** `c0001 c0001 c0178 c0178`  **거부된 인용:** 0

**답변:** One account: as a Mississippi steamboat pilot, Clemens liked the rivermen's call "Mark twain," meaning two fathoms of water — a safe depth. The other: as a Nevada newspaper reporter he'd enter a saloon and call "Mark twain," meaning mark two more drinks on his tab.

### q08 (흩어짐) — top-3 O, 정확 O

**질문:** How did Mark Twain first come across Joan of Arc as a boy, and what did he say to the Archbishop of Orleans about being near her in the next life?

**검색된 청크:** `c0089(p.25-26) c0088(p.25) c0183(p.41-43)`  **인용된 청크:** `c0088 c0089`  **거부된 인용:** 0

**답변:** As a boy he chased a stray page blowing down the street, caught it, and found it came from a biography of Joan of Arc, which set him reading about her. He told the Archbishop of Orléans he would be "perfectly satisfied" in the next life if he were near Joan of Arc and as far as possible from her enemies.

### q09 (없음) — top-3 n/a, 정확 O

**질문:** What does the book say about Mark Twain being the first author to submit a typewritten manuscript to a publisher?

**검색된 청크:** `c0066(p.19) c0067(p.19) c0183(p.41-43)`  **인용된 청크:** `—`  **거부된 인용:** 0

**답변:** Not in this book.

### q10 (없음) — top-3 n/a, 정확 O

**질문:** According to the book, how did Mark Twain react to receiving his honorary degree from Oxford in 1907?

**검색된 청크:** `c0061(p.18) c0183(p.41-43) c0064(p.19)`  **인용된 청크:** `—`  **거부된 인용:** 0

**답변:** Not in this book.

