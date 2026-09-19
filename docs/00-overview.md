# Overview

## Mission

An internal agent whose intuition is a predictive database. Every morning it
answers three questions about a real sales pipeline:

1. Who should be called in today's call window, and why?
2. What is the opener, grounded in how statistically similar contacts responded?
3. What did yesterday's outcomes change?

It learns from every logged outcome: a call result recorded today reorders
tomorrow's queue.

## Why it exists

Most agent stacks have reasoning (an LLM) and memory (retrieval). Almost none
have a learning layer: nothing in them gets statistically better from
operational outcomes, and nothing attaches a calibrated probability to
"call this person first." This repo is the missing third faculty, run on the
company's own pipeline before it is recommended to anyone else.

LLMs gave your agent reasoning. RAG gave it memory. Aito gives it intuition.

## Success metric

Exactly one: the operator's call windows execute with less friction than
they did before the brief existed. Stars, features, and coverage are not
success metrics for Head 1.

## Scope

In scope: schema, loaders, MCP server, morning brief prompt, outcome
logging, the read-only dashboard (Segment 360, predictive funnels for sales
and website/acquisition, and the messaging-formula post scorer), booktests.

Out of scope (gated or banned, see CLAUDE.md and `05-phases.md`): the
external support agent (Head 2), outbound automation of any kind,
scheduling, invoicing, marketing.

## Lineage

The operational pattern behind [agent.aito.ai](https://agent.aito.ai),
applied to the company's own sales operation. Schema lineage: the decision-
record design is a simplification of an earlier internal prototype; its
pattern-extraction machinery was deleted because Aito's inference replaces
it natively.
