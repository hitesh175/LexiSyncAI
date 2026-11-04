# Five-minute demo

| Time | Show | Say |
|---|---|---|
| 0:00–0:45 | Architecture diagram | Each claim points to an exact excerpt and a page. The system checks evidence before showing an answer. |
| 0:45–1:30 | Upload and index | Show page structure and explain how the index handles clause boundaries and flags scans. |
| 1:30–2:25 | Factual question | Ask what §107(4) considers. Open the cited page and point to the quoted factor. |
| 2:25–3:30 | Multi-hop question | Ask which right covers reproducing copies and how qualifying fair use affects infringement. Open both source pages. |
| 3:30–4:15 | Unanswerable question | Ask for the royalty rate of the Acme–Northwind contract. Show the abstention and searched documents. |
| 4:15–5:00 | Evaluation | Show recall by configuration, abstention counts and observed latency from the run. |

For the unseen exam PDF, substitute its actual headings and questions. Warm the retrieval models and Ollama before the exam. If a draft abstains on an answerable item, inspect the evidence coverage before attributing the failure to the generator.

## Theory Q&A

- **Why BM25 and dense?** Lexical retrieval preserves literal identifiers and dense retrieval can find related wording. Rank fusion combines signals without putting raw scores on the same scale.
- **Why rerank?** A cross-encoder attends jointly to question and passage, at the cost of one pairwise score per candidate.
- **Why can an exact quote still be misleading?** A quote proves the text exists. It might omit a qualifying clause, fail to imply the claim, or support only one part of a multi-hop answer.
- **What does recall@10 measure?** The fraction of annotated evidence units recovered within ten results, averaged over answerable questions. Complete coverage measures whether every required unit appears.
- **How does abstention fail?** Missing retrieval, ambiguous document structure, overly strict quote matching, or incorrect verifier judgments can all produce false abstentions.
