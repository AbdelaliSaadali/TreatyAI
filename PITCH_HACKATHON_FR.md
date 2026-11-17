# TreatyAI — Présentation Hackathon / PFE

## Pitch oral (environ 3 minutes)

Bonjour, nous vous présentons TreatyAI.

Aujourd'hui, dans une entreprise, les agents IA peuvent être très efficaces individuellement. Mais quand plusieurs agents prennent des décisions sur un même client, leurs actions peuvent entrer en conflit.

Imaginez un client qui vient de subir un problème de facturation. L'agent Service Client veut lui accorder 100 dirhams de compensation. L'agent Fidélisation propose aussi 100 dirhams pour éviter son départ. Au même moment, l'agent Marketing souhaite lui envoyer une promotion. Le problème, c'est que l'entreprise n'a autorisé que 150 dirhams de compensation pour ce client, et qu'une réclamation critique est encore ouverte.

Chaque agent peut avoir une bonne intention, mais le résultat global peut être mauvais : dépassement du budget et mauvaise expérience client.

C'est précisément le problème que TreatyAI cherche à résoudre.

Notre projet est une couche de gouvernance entre les agents autonomes et les systèmes métiers. Au lieu de laisser chaque agent exécuter seul sa décision, TreatyAI reçoit leurs propositions sous forme de contrats structurés, détecte les conflits et calcule un plan cohérent en respectant des règles non négociables.

Dans notre exemple, le moteur peut approuver 100 dirhams pour le Service Client, ajuster la proposition de Fidélisation à 50 dirhams et reporter la promotion Marketing jusqu'à la résolution de la réclamation.

Nous avons aussi intégré un laboratoire de négociation basé sur Groq. De vrais modèles de langage peuvent jouer le rôle d'agents spécialistes, analyser les conflits et proposer des compromis. Mais un point est essentiel : **l'IA propose, le moteur de règles vérifie et autorise**. Le modèle de langage ne peut pas contourner le consentement du client, les limites budgétaires ou les autorisations de chaque agent.

Pour renforcer la fiabilité, nous utilisons un vérificateur indépendant, une transaction SQLite contre les conflits simultanés, des clés d'idempotence et des reçus audités avec une chaîne de hachage SHA-256.

Nous avons développé des tests de sécurité, des simulations aléatoires et des cas comparés à une optimisation exhaustive. Notre benchmark initial reste synthétique : il démontre le fonctionnement de nos règles, mais ne prouve pas une performance en production.

Notre ambition est d'intégrer cette couche à Salesforce Agentforce, afin de faire évoluer l'automatisation individuelle vers une véritable coordination fiable entre agents IA en entreprise.

TreatyAI : **Many agents. One governed outcome.**

## Démonstration recommandée (4 à 5 minutes)

1. **Le problème** — ouvrir Decision room et présenter les demandes de Service, Fidélisation et Marketing face au budget de 150 MAD.
2. **Le graphe** — expliquer la ressource partagée et la priorité de la réclamation critique.
3. **La résolution** — montrer 100 + 50 MAD et le report Marketing. Insister sur le fait qu'un modèle LLM ne peut pas autoriser une action.
4. **La preuve** — afficher les six vérifications indépendantes, le reçu et son empreinte SHA-256.
5. **La concurrence** — lancer deux demandes simultanées de 100 MAD chacune contre un budget de 150 MAD. Le total ne doit pas dépasser 150 MAD.
6. **Évaluation** — ouvrir TreatyBench et présenter le baseline synthétique, ses limites et les tests de propriétés.
7. **Groq optionnel** — ouvrir AI Agent Lab uniquement si la connexion au fournisseur a été vérifiée. Présenter les intentions générées, la médiation et les contre-offres. Si le fournisseur est indisponible, la démonstration hors ligne reste complète.

## Questions probables du jury

**Pourquoi est-ce différent d'un orchestrateur d'agents ?**
Un orchestrateur organise qui fait quoi et dans quel ordre. TreatyAI se concentre sur la cohérence et la sécurité des décisions prises ensemble, avant leur exécution.

**Pourquoi ne pas laisser les agents discuter entre eux et voter ?**
Un accord entre plusieurs modèles ne garantit pas le respect d'un budget, du consentement client ou des autorisations. Nos règles et notre vérification indépendante constituent une barrière technique supplémentaire.

**L'intelligence artificielle est-elle réellement utilisée ?**
Le laboratoire Groq dispose d'une intégration LLM, de contrats JSON stricts et d'une médiation structurée. Une démonstration de vrais appels ne doit être annoncée que si une exécution a réellement réussi avec la clé configurée. Le moteur métier fonctionne aussi sans LLM.

**L'intégration Salesforce est-elle opérationnelle ?**
Le projet inclut le code d'un adaptateur Apex et un contrat HTTP. La compilation, le déploiement et les tests dans une organisation Salesforce sont confiés à notre coéquipier. Nous ne devons pas prétendre que cette intégration fonctionne avant sa validation réelle.

**Est-ce prêt pour une entreprise ?**
C'est un prototype de recherche fonctionnel, pas un produit de production. Les étapes suivantes comprennent l'authentification des agents, l'isolation des clients, une base distribuée, un outbox pour les effets externes, la signature des reçus et davantage de benchmarks indépendants.

**Vos résultats de benchmark sont-ils fiables ?**
Nous distinguons strictement les résultats synthétiques et les performances réelles. Les chiffres actuels portent sur 30 cas déterministes, avec une baseline volontairement simple. Nous avons aussi des tests aléatoires et une comparaison exhaustive sur de petits cas pour limiter les erreurs de l'optimiseur.

**Quel est le potentiel PFE ?**
Un PFE de 4 à 6 mois peut travailler sur une intégration Agentforce sécurisée, la formalisation des règles par SMT/CP-SAT, la vérification d'invariants, la tolérance aux pannes et une évaluation expérimentale plus large.

## Discipline de démonstration

- Ne jamais dire qu'une action Salesforce réelle a été exécutée sans preuve.
- Ne pas présenter un benchmark synthétique comme une performance en production.
- Ne pas appeler la chaîne SHA-256 une signature électronique.
- Ne pas présenter la recherche bornée de l'optimiseur comme une preuve d'optimalité générale.
- Afficher clairement les modes LOCAL / GROQ / SALESFORCE pour éviter les ambiguïtés.
