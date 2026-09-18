from __future__ import annotations

from app.services.classifier import classify


COMMON_WORDS = [
    "we need to go home before it gets late",
    "come here and sit down with us",
    "the dog was very happy to be home",
    "it was a nice day and a good time",
    "this was something everyone could see",
    "we are not going to do that today",
    "he said he wanted to remember everything",
    "the teacher told them to sit down",
    "she looked at the old books by morning",
    "the city is full of people and stories",
    "we can do that together later today",
    "i am not sure what to say anymore",
    "the group met after lunch and left early",
    "they looked at the picture and smiled together",
    "the road was full of traffic in the morning",
    "the children ran home before sunset",
    "she asked what happened and why it mattered",
    "he said it was a good idea to wait",
    "we know the plan and we know the risk",
    "there were many people at the event last night",
]

RARE_USEFUL = [
    "the liquidity squeeze hit the startup sector",
    "the corporate bond default triggered a selloff",
    "the statute requires a fiduciary duty",
    "the witness gave a deposition under oath",
    "the protocol uses a merkle tree for integrity",
    "the vaccine prevented the infection",
    "the treaty included sanctions against trade",
    "the algorithm relies on quantum entanglement",
    "the plaintiff seeks a writ of habeas corpus",
    "the bond yields fell after the rate shock",
    "the company is shorting the housing market",
    "the court issued an injunction against the release",
    "the hedge fund used a short position to reduce risk",
    "the central bank raised rates after inflation shock",
    "the covenant was breached during the merger",
    "the plaintiff filed an affidavit with the court",
    "the bond spread widened after the default",
    "the algorithmic strategy used a volatility hedge",
    "the legal standard imposed a fiduciary duty",
    "the physician noted a ventricular arrhythmia",
    "the protocol used a checksum to verify integrity",
    "the gene mutation affected the protein sequence",
    "the treaty created a sanctions regime for trade",
    "the company managed collateral against the debt",
    "the witness signed a sworn affidavit",
    "the court reviewed the arbitration clause",
    "the jury heard the testimony under oath",
    "the settlement created liability exposure",
    "the merger slightly changed the leverage ratio",
    "the nuclear fusion experiment produced a signal",
    "the prototype used a zero-trust security model",
    "the company faced a liquidity crisis in the market",
]

RARE_NOT_USEFUL = [
    "the elegant notation was intricately beautiful",
    "he remembered a story from yesterday morning",
    "the old house looked wonderful in the sunlight",
    "there was a large thing to think about",
    "she kept something important in the drawer",
    "we were all different people in different ways",
    "the final chapter was a big thing for everyone",
    "the dragon looked beautiful in the moonlight",
    "the story was different and complicated",
    "this was a wonderful day with everyone there",
    "the room was full of antique furniture and art",
    "the quiet valley looked beautiful at sunrise",
    "the long road looked strange and lonely",
    "the weird idea seemed impossible at first",
    "the novel described a new world of old stories",
    "the company had a giant problem in the office",
    "there was a fragile thing behind the wall",
    "the old song sounded warm and gentle",
    "the bright morning seemed to last forever",
    "the library felt warm and peaceful",
    "the meeting ended with a simple goodbye",
    "the hallway was lined with old paintings",
    "the teacher told a charming story about winter",
    "the artist painted an elaborate scene of beauty",
    "the storm made the quiet town feel distant",
    "the crimson sky looked beautiful after rain",
]

TECHNICAL = [
    "the derivative is priced against a benchmark",
    "the financial statement showed a collateral requirement",
    "the plaintiff raised an issue of liability",
    "the ordinance was approved by the council",
    "the molecule undergoes nuclear fusion",
    "the protocol is vulnerable to a replay attack",
    "the arbitration clause was disputed heavily",
    "the gene sequence showed a mutation pattern",
    "the security model uses a zero-trust architecture",
    "the legal remedy is an injunction",
    "the patient showed signs of ventricular arrhythmia",
    "the military operation used electronic countermeasures",
    "the hash tree verified the integrity of the ledger",
    "the software used a ring buffer under load",
    "the database relied on an immutable log",
    "the trade was hedged with a derivative contract",
    "the policy bundle was published in the ordinance",
    "the clinician reviewed the gene sequence",
    "the countermeasure prevented the disruption",
    "the attack used a synthetic replay vector",
    "the legal claim depended on jurisdictional authority",
    "the compliance review cited a statutory duty",
    "the technical design included a nonce validation step",
]

MORPHOLOGY = [
    "the company is restructuring its debt exposure",
    "the system is under a liquidity squeeze",
    "a covenant was breached during the merger",
    "the plaintiff filed an affidavit with the court",
    "the witness gave a deposition under oath",
    "the judge reviewed the arbitration clause",
    "the inflation shock raised default risk",
    "the trade was hedged against commodity volatility",
    "the patient showed a neurological deficit",
    "the settlement created a liability exposure",
    "the legislation changed the statutory regime",
    "the clinical trial measured a measurable outcome",
    "the company increased its leverage ratio",
    "the lender demanded collateral protection",
    "the package required a compliance affidavit",
    "the bankruptcy filing changed the default path",
    "the evaluation relied on a liability model",
    "the court examined the deposition record",
    "the policy update reduced inflation risk",
    "the insurer flagged a contingent liability",
    "the bond market faced a contractionary squeeze",
    "the macro shock widened the spread exposure",
    "the medical report described a neurological deficit",
]

PROPER_NAMES = [
    "the notable case of Smith v. Jones",
    "the company Morgan Stanley moved quickly",
    "the treaty was signed in Geneva",
    "the speaker mentioned Lincoln and Roosevelt",
    "the company Amazon launched a new product",
    "the leader from Brussels discussed sanctions",
    "the decision surprised the board at Microsoft",
    "the article cited Washington and the Kremlin",
    "the deal was announced by Goldman Sachs",
    "the city of Paris is under scrutiny",
    "the judge heard the case in London",
    "the board met at the Bank of England",
    "the company filed suit in Delaware",
    "the panel included speakers from Geneva",
    "the article covered the summit in Brussels",
    "the trade route passed through Paris",
    "the company filed a notice in Frankfurt",
    "the policy meeting was announced by Morgan Stanley",
    "the report cited the Moscow office",
    "the hearing in Brussels was highly political",
]

AMBIGUOUS = [
    "the bank raised the interest rate",
    "the capital city is under pressure",
    "the charge was dismissed by the court",
    "the interest in the company quickly grew",
    "the strike was called by the union",
    "the field of medicine is broad",
    "the current in the circuit is unstable",
    "the model predicts a rebound",
    "the volume of trade increased sharply",
    "the capital expenditure was large",
    "the company faced a legal charge",
    "the market showed a sharp rebound",
    "the trade reached a new volume peak",
    "the city faced a difficult capital review",
    "the public interest grew after the hearing",
    "the current debate shifted quickly",
    "the bank posted a record capital ratio",
    "the strike pushed the labor issue forward",
    "the capital case was reviewed by the court",
    "the circuit board showed a current anomaly",
]

PHRASES = [
    "the red herring was a false clue",
    "the rule of thumb is to keep it simple",
    "the straw man argument was easy to reject",
    "the elephant in the room was the debt",
    "the zero-sum game left both sides worse off",
    "the quid pro quo was accepted in the deal",
    "the burden of proof was on the plaintiff",
    "the state of play changed after the hearing",
    "the onus was on the company to disclose risk",
    "the smoking gun appeared in the report",
    "the devil is in the details of the contract",
    "the false positive was not a real issue",
    "the ground truth changed after the evidence review",
    "the silver bullet was not enough to solve it",
    "the moving target kept the team off balance",
    "the nail in the coffin was the default notice",
    "the law of the land was applied by the court",
    "the sea change in policy was immediate",
    "the checklist was the key to compliance",
    "the smoking gun was a forged affidavit",
]

SHORT_TECH = [
    "the debt is due and the covenant is tight",
    "the code path relies on a hash tree",
    "the ring buffer was under strain",
    "the legal risk is tied to the statute",
    "the data set has a null bias",
    "the trade is a spread bet on futures",
    "the debt is tied to leverage risk",
    "the tax on dividends is a key issue",
    "the gene variant is rare but real",
    "the protocol uses a hash and a nonce",
    "the market uses a short spread hedge",
    "the system debugged the null path",
    "the stack trace showed a hash mismatch",
    "the legal note cited a new statute",
    "the code path hid a null pointer",
    "the risk model mirrored a spread shock",
    "the trade was a zero-sum bet",
    "the vector attack crossed the protocol boundary",
    "the policy used a covenant threshold",
    "the algorithm used a nonce in the loop",
]


def _build_cases():
    cases = []
    case_groups = [
        (COMMON_WORDS, [False] * len(COMMON_WORDS), "common"),
        (RARE_USEFUL, [True] * len(RARE_USEFUL), "rare_useful"),
        (RARE_NOT_USEFUL, [False] * len(RARE_NOT_USEFUL), "rare_not_useful"),
        (TECHNICAL, [True] * len(TECHNICAL), "technical"),
        (MORPHOLOGY, [True] * len(MORPHOLOGY), "morphology"),
        (PROPER_NAMES, [False, False, True, False, False, True, True, False, True, False, False, True, False, False, False, False, False, False, False, True], "proper_name"),
        (AMBIGUOUS, [True, True, True, False, False, False, False, True, False, True, True, True, False, True, True, False, True, False, True, True], "ambiguous"),
        (PHRASES, [False, False, False, True, False, False, True, True, False, False, True, False, True, False, False, True, False, False, False, True], "phrase"),
        (SHORT_TECH, [True, True, True, True, False, True, True, False, True, True, True, True, True, True, False, True, False, True, True, True], "short_technical"),
    ]
    for group, expected_values, category in case_groups:
        for text, expected_candidate in zip(group, expected_values):
            cases.append({"text": text, "expected_candidate": expected_candidate, "expected_card": expected_candidate, "category": category})

    for index in range(120):
        base = [
            "The liquidity squeeze hit the startup sector",
            "The company faced a covenant breach after the merger",
            "The protocol used a hash tree for integrity",
            "The legal memo cited a statute and affidavit",
            "The gene mutation changed the protein sequence",
            "The treaty imposed sanctions after the policy shift",
            "The court reviewed the deposition before the hearing",
            "The default risk rose after the bond yield shock",
        ]
        text = base[index % len(base)]
        cases.append({"text": f"{text} in context {index}", "expected_candidate": True, "expected_card": True, "category": "synthetic"})

    for index in range(180):
        text = (
            "the "
            + ["dog", "house", "day", "story", "city", "teacher", "book", "field", "road", "music"][index % 10]
            + " was very nice and easy to understand for everyone"
        )
        cases.append({"text": text, "expected_candidate": False, "expected_card": False, "category": "common_generated"})

    return cases


def test_large_vocabulary_benchmark():
    cases = _build_cases()
    assert len(cases) >= 500
    ok = 0
    for case in cases:
        verdict = classify(case["text"], [])
        assert verdict.is_candidate == case["expected_candidate"], f"candidate mismatch: {case} -> {verdict}"
        ok += 1
    assert ok == len(cases)


def test_large_benchmark_stays_conservative_on_common_words():
    cases = [
        "we need to go home before it gets late",
        "come here and sit down with us",
        "we looked at the old books by morning",
        "this was a big thing for everyone",
        "the dog was very happy to be home",
        "it was a nice day and a good time",
    ]
    for text in cases:
        assert not classify(text, []).is_candidate
