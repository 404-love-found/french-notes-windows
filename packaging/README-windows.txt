FrenchNotes 0.1.3 — Notes de français hors ligne pour Windows

Systèmes compatibles : Windows 10 / 11, 64 bits (x64).
Aucune installation de Python n'est nécessaire pour utiliser le logiciel.
L'interface est entièrement en français. Vos fichiers CSV et Word restent sur votre ordinateur.

Démarrage
1. Version installable : lancez FrenchNotes-Setup-0.1.3.exe et suivez l'assistant.
   L'installation concerne uniquement votre compte et ne demande normalement pas de droits administrateur.
   Ouvrez ensuite FrenchNotes depuis le menu Démarrer ou le raccourci du bureau.
2. Version sans installation : extrayez FrenchNotes-0.1.3-Windows-x64.zip, puis ouvrez FrenchNotes.exe.
   Conservez le dossier licenses avec le programme ; il contient les licences des logiciels tiers.

Saisie et exportation
1. Dans l'onglet « Saisie par lot », saisissez un mot ou une phrase en français par ligne.
2. Cliquez sur « Analyser » et vérifiez la catégorie proposée.
   Utilisez « Classer la sélection » pour corriger manuellement la catégorie : « Mot » ou « Phrase ».
   « À ajouter » désigne une nouvelle note ; « Déjà dans le CSV » désigne une note déjà enregistrée.
   « Doublon du lot » désigne une répétition dans la saisie.
3. Cliquez sur « Enregistrer les nouvelles notes » pour enregistrer uniquement les éléments absents du CSV
   et éviter les doublons dans la saisie en cours.
   Retrouvez les notes sauvegardées dans l'onglet « Notes enregistrées ».
4. Cliquez sur « Tout exporter vers Word » pour exporter toutes les notes enregistrées,
   regroupées par catégorie, dans un fichier local .docx.
   Ouvrez ce fichier avec Microsoft Word ou un autre logiciel compatible avec le format .docx.

Détection des doublons
La comparaison ignore les espaces en début et en fin, les espaces répétés et les différences de casse.
Elle conserve les différences d'accents et de ponctuation.
La classification utilise des règles locales ; vous pouvez ajuster la catégorie des expressions composées.

Emplacement des données
CSV par défaut : %LOCALAPPDATA%\FrenchNotes\notes.csv
Préférences : %LOCALAPPDATA%\FrenchNotes\settings.json
Cliquez sur « Choisir un CSV » pour utiliser un autre fichier local.
Cliquez sur « Ouvrir le dossier » pour accéder au dossier de votre CSV.
La version sans installation utilise aussi le dossier de données par défaut indiqué ci-dessus.
Les documents Word sont enregistrés à l'emplacement choisi lors de l'exportation.
Une mise à jour ou une désinstallation conserve vos notes.
Sauvegardez vos fichiers CSV et Word importants avant de supprimer le logiciel.

Vérification des fichiers
SHA256SUMS.txt contient les empreintes SHA-256 des fichiers publiés.
Dans PowerShell, exécutez Get-FileHash .\FrenchNotes.exe -Algorithm SHA256, puis comparez le résultat.
Le programme et le programme d'installation ne disposent pas encore d'une signature numérique.
Windows peut donc afficher un avertissement indiquant que l'éditeur est inconnu.

Projet et mises à jour
https://github.com/404-love-found/french-notes-windows
https://github.com/404-love-found/french-notes-windows/releases
