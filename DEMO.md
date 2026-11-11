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

## Verified GDPR rehearsal

Create a case with the four PDFs in the EU GDPR Source Pack. For the cross-document step, use this tested question:

> What are the maximum fines under Article 83(4) and Article 83(5), and which three inputs does step 2 of EDPB Guidelines 04/2022 section 2.2 use for the starting amount?

Open the two statutory citations on PDF pages 82 and 83 of the regulation, then open PDF page 9, section 2.2 of the EDPB fines guidance. This shows the distinction between the legal maximum and the guidance on the starting amount. Use the speeding question for the out-of-scope example.

The tested answer included some repeated citations. [RESULTS.md](RESULTS.md) separates earlier baselines from later retrieval and citation checks. The GDPR rehearsal is a separate targeted check.

For a separately tested single-PDF walkthrough with timed questions, see [Single-PDF rehearsal](rehearsal/README.md).
