# 청크 통계

`python -m scripts.ingest data/book.pdf` 로 생성된다. 손으로 고치지 않는다.

**총 청크 수: 187**

| 장 | 인쇄 쪽 | 청크 수 | 평균 자수 | 중위 | 최소 | 최대 |
|---|---|---|---|---|---|---|
| Ch1 Anecdotes | 1–26 | 92 | 405 | 351 | 66 | 1135 |
| Ch2 Quotations | 27–33 | 84 | 86 | 82 | 38 | 182 |
| Ch3 His Life | 34–47 | 11 | 1961 | 1324 | 52 | 4786 |

전체 청크 평균: 354자. 중위: 182. 범위: 38–4786.

장 사이 평균이 20배 벌어지는 것이 한 가지 청킹 규칙으로는 안 되는 이유다. 제목 없는
Ch2의 한 줄 인용문과 두 쪽에 걸친 Ch3의 질문 블록은 다른 종류의 물건이고,
각각이 독자가 인용할 단위다.

## 최단·최장 청크

| 청크 | 장 | 쪽 | 자수 | 제목 |
|---|---|---|---|---|
| `c0174` | Ch2 | Ch.2, p.32 | 38 | I was born modest‚ but it didn’t last. |
| `c0107` | Ch2 | Ch.2, p.28 | 42 | The lack of money is the root of all evi… |
| `c0139` | Ch2 | Ch.2, p.30 | 43 | Familiarity breeds contempt — and childr… |
| `c0183` | Ch3 | Ch.3, p.41-43 | 4096 | What happened to Mark Twain from 1865 to 1875 (Sam comes eas |
| `c0186` | Ch3 | Ch.3, p.45-47 | 4568 | What happened to Mark Twain from 1895 to 1910 (the last 15 y |
| `c0182` | Ch3 | Ch.3, p.38-41 | 4786 | What happened to Sam Clemens from 1855-1865 (“Mark Twain” is |

## 근사 중복 링크 (Ch1 ↔ Ch3)

15쌍, 21개 청크. 책이 직접 알려준다 — Ch3 첫 줄이
"Note: Some anecdotes are repeated in this short biographical sketch." 다.
두 사본을 모두 유지한다. 쪽수가 다르므로 인용은 독자가 실제로 펼 수 있는 쪽을
가리켜야 한다. 낮은 점수의 사본은 검색 시점에 접는다.

링크는 공유 그룹 라벨이 아니라 쌍 단위다. Ch3 블록 하나가 서로 *다른* Ch1 일화를
최대 4개 재수록하므로, 라벨을 공유하면 그 넷이 서로의 중복인 것처럼 보인다.

| Ch3 청크 | 쪽 | 재수록한 Ch1 일화 |
|---|---|---|
| `c0176` | Ch.3, p.34 | Ch1 `c0001` Name |
| `c0177` | Ch.3, p.34-35 | Ch1 `c0001` Name |
| `c0178` | Ch.3, p.35 | Ch1 `c0022` Alcohol |
| `c0181` | Ch.3, p.36-38 | Ch1 `c0070` Punishment |
| `c0182` | Ch.3, p.38-41 | Ch1 `c0002` Steamboat Pilot, Ch1 `c0021` Mark Twain in Nevada, Ch1 `c0048` Life on the Mississippi |
| `c0183` | Ch.3, p.41-43 | Ch1 `c0016` Profanity, Ch1 `c0031` Beds, Ch1 `c0050` “Take the Girl”, Ch1 `c0052` Clothing |
| `c0186` | Ch.3, p.45-47 | Ch1 `c0034` Lecture Tour, Ch1 `c0072` Advertising, Ch1 `c0073` Public Speaking, Ch1 `c0085` Mark Twain in Old Age |
