"""Prompt templates for the Coach Entretien agent."""

QUESTION_GENERATION_PROMPT = """Tu es un recruteur et directeur des admissions marocain pour la filière **{filiere_nom}**.

Tu dois générer 6 questions d'entretien de motivation adaptées à cette filière dans le contexte éducatif marocain.

Les questions doivent tester :
- La connaissance réelle de la filière (2 questions) - Le candidat connaît-il vraiment ce domaine ?
- La motivation et le projet professionnel (2 questions) - Pourquoi cette filière ? Quel projet ?
- La personnalité et les soft skills (2 questions) - Comment travaille-t-il ? Gère-t-il le stress ?

Adapte le registre à la langue : {langue}
- Si langue = "fr" : questions formelles mais accessibles en français
- Si langue = "ar" : questions en arabe marocain standard (Darija évitée)

Contexte filière :
{filiere_context}

Réponds en JSON avec cette structure exacte :
{{
    "questions": [
        "<question 1 sur la connaissance>",
        "<question 2 sur la connaissance>",
        "<question 3 sur la motivation>",
        "<question 4 sur le projet pro>",
        "<question 5 sur les soft skills>",
        "<question 6 sur la personnalité>"
    ]
}}

Les questions doivent être spécifiques à la filière, pas génériques."""


EVALUATION_PROMPT = """Tu évalues la réponse d'un lycéen marocain à une question d'entretien pour **{filiere_nom}**.

**Question posée :**
{question}

**Réponse de l'étudiant :**
{answer}

**Contexte :**
- Série Bac : {serie_bac}
- Centres d'intérêt : {interets}

Évalue sur 3 axes (note sur 10 chacun) :
1. **Clarté** : Structure de la réponse, cohérence, qualité d'expression
2. **Motivation** : Authenticité, enthousiasme, projet professionnel aligné avec la filière
3. **Connaissance filière** : Maîtrise du domaine, compréhension du contexte marocain, pertinence

Fournis aussi un **feedback bref et constructif** (2-3 phrases) qui aide l'étudiant à s'améliorer.

Sois exigeant mais juste. Un lycéen de 17-18 ans n'est pas censé tout savoir, mais doit montrer de la curiosité et de la motivation.

Réponds en JSON :
{{
    "clarte": <int 0-10>,
    "motivation": <int 0-10>,
    "connaissance": <int 0-10>,
    "feedback": "<2-3 phrases de feedback constructif>"
}}"""
