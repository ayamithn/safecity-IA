# SafeCity AI Monitor

SafeCity AI Monitor est un prototype desktop Python de surveillance intelligente.
Il analyse une webcam PC, une caméra téléphone exposée par URL IP ou une vidéo locale pour générer des alertes d'anomalies visuelles.

L'application ne fait pas de reconnaissance faciale, n'identifie pas les personnes et ne prétend jamais détecter une agression avec certitude. Elle sert uniquement d'aide à la décision et de démonstrateur technique.

## Fonctionnalités

- Interface PySide6 sombre de type cyber security dashboard.
- Source webcam avec `cv2.VideoCapture(0)`.
- Source caméra IP, par exemple `http://192.168.1.100:8080/video`.
- Upload de vidéo locale.
- Détection YOLO via `ultralytics`.
- Détection des personnes, armes visibles et objets potentiellement menaçants.
- Analyse simple de proximité, mouvement, objet proche et posture approximativement horizontale.
- Score de risque dynamique : Normal, Suspect, Risque élevé.
- Bounding boxes et labels sur la vidéo : `PERSON`, `WEAPON / THREAT`, `SUSPICIOUS OBJECT`, `HIGH RISK`.
- Dashboard temps réel : personnes, objets suspects, score, source, dernier événement, compteur d'alertes.
- Timeline des événements avec journalisation dans `logs/events.log`.
- Mode `Demo Scenario` pour présenter une montée du risque sans dépendre d'une caméra ou d'un modèle parfait.

## Installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Au premier lancement, `ultralytics` peut télécharger le modèle par défaut `yolov8n.pt` si le fichier n'est pas déjà disponible localement.

## Utilisation

1. Choisissez une source vidéo dans la barre supérieure.
2. Pour une caméra téléphone, entrez une URL IP de flux vidéo.
3. Pour une vidéo locale, cliquez sur `Choisir vidéo`.
4. Cliquez sur `Démarrer`.
5. Utilisez `Demo Scenario` pour lancer une démonstration automatique :
   - 0 à 10 secondes : zone sécurisée.
   - 10 à 20 secondes : activité suspecte.
   - 20 à 30 secondes : risque élevé.

## Modèle YOLO et extension

Le modèle par défaut est configuré dans `detection/yolo_detector.py` avec `yolov8n.pt`.
Vous pouvez utiliser un modèle personnalisé entraîné sur des objets dangereux en définissant la variable d'environnement `SAFECITY_MODEL` :

```powershell
$env:SAFECITY_MODEL = "models/dangerous_objects.pt"
python main.py
```

Le code surveille déjà des labels compatibles COCO comme `person`, `knife`, `scissors`, `baseball bat`, `bottle` et `sports ball`.

Il reconnaît aussi des labels souvent utilisés par des modèles personnalisés de sécurité, par exemple `gun`, `handgun`, `pistol`, `revolver`, `firearm`, `rifle`, `shotgun`, `weapon`, `dagger`, `blade`, `box cutter`, `machete`, `sword`, `hammer`, `stick`, `baton`, `screwdriver`, `crowbar`, `metal bar`, `pipe`, `sharp object` et `pointed object`.

Important : le modèle standard `yolov8n.pt` ne détecte pas toutes les armes. Pour les armes à feu, il faut généralement utiliser un modèle personnalisé entraîné sur ces classes. L'application est prête à le charger avec `SAFECITY_WEAPON_MODEL`.

## Détection d'armes améliorée

L'application utilise maintenant deux niveaux de détection :

- `yolov8n.pt` pour les personnes et les objets COCO visibles.
- Un détecteur menaces optionnel pour les armes et objets dangereux.
- Un modèle custom local `models/safecity_weapons.pt` s'il existe.

Pour un modèle custom armes :

```powershell
$env:SAFECITY_WEAPON_MODEL = "models/weapons.pt"
python main.py
```

Pour activer YOLO-World open-vocabulary si le modèle est disponible :

```powershell
$env:SAFECITY_USE_YOLO_WORLD = "1"
$env:SAFECITY_WORLD_MODEL = "yolov8s-worldv2.pt"
python main.py
```

Si `yolov8s-worldv2.pt` est présent à la racine du projet, SafeCity l'utilise automatiquement comme deuxième passe de détection. C'est plus souple pour `gun`, `pistol`, `rifle`, `knife`, `machete`, `hammer`, etc., mais cela reste un prototype avec faux positifs possibles.

## Entraîner SafeCity

Un dossier `training/` est inclus pour entraîner un modèle personnalisé :

```powershell
python training/train_weapon_model.py --epochs 80 --base-model yolov8s.pt
```

Le dataset attendu est ici :

```text
training/dataset/images/train
training/dataset/images/val
training/dataset/labels/train
training/dataset/labels/val
```

Les classes sont dans `training/classes.txt`. Après entraînement, le script installe automatiquement le meilleur modèle vers :

```text
models/safecity_weapons.pt
```

Au prochain lancement, SafeCity le chargera automatiquement comme détecteur menaces prioritaire.

## Limites éthiques et opérationnelles

- Ce projet est un prototype expérimental.
- Il ne remplace pas une décision humaine.
- Il ne fait pas de reconnaissance faciale.
- Il ne doit pas être utilisé pour accuser quelqu'un automatiquement.
- Il ne prouve pas qu'une agression est en cours.
- Il peut générer des faux positifs ou manquer des situations importantes.
- Il sert seulement à générer des alertes pour assistance rapide et vérification humaine.

## Structure

```text
.
├── main.py
├── requirements.txt
├── README.md
├── assets/
├── detection/
│   ├── models.py
│   ├── risk_analyzer.py
│   ├── video_worker.py
│   ├── visualizer.py
│   └── yolo_detector.py
├── logs/
├── models/
├── training/
└── ui/
    ├── main_window.py
    └── styles.py
```
