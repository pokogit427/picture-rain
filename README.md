# Picture Rain

йЭyш§yЫ§uзвќзD"йЭyш§yЫ§uзвќз\єw^~)Юt»§uзвќз@єw^~)Юt»§uзвќзuєw^~)Юt+§uзвќз\єw^~)ЮvйЭyш§yФ.

##+§uзвќз\єw^~)Юt+§uзвќзdєw^~)Юu

єw^~)ЮvйЭyш§yЬ єw^~)ЮvйЭyш§yЫ§uзвќзXєw^~)ЮvйЭyш§yШ єw^~)ЮvйЭyш§yЫ§uзвќзD"йЭyш§yЫ§uзвќз|"йЭyш§yЫ§uзвќзPєw^~)Юt+§uзвќзdєw^~)Юt+§uзвќзEєw^~)ЮvйЭyш§yФ єw^~)ЮvйЭyш§yЫ§uзвќзiєw^~)ЮvйЭyш§yФ.

```bash
cd /home/daks/projects/picture-rain
docker compose up -d --build
```
§uзвќзAєw^~)ЮvйЭyш§yР API·DB"йЭyш§yЫ§uзвќзpєw^~)Юt+§uзвќзUєw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt.

```bash
docker compose ps
curl http://localhost:8000/health
curl http://localhost:8000/photos
```

йЭyш§yЫ§uзвќзDєw^~)Юt+§uзвќзEєw^~)ЮvйЭyш§yЫ§uзвќзXєw^~)Юt+§uзвќз@єw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt.

```bash
curl -F "file=@/path/to/photo.png" http://localhost:8000/photos
curl -X POST -G -d width=800 -d height=800 -d output_format=webp \
  http://localhost:8000/photos/<photo-id>/transform
```
§uзвќз\єw^~)ЮvйЭyш§yФ єw^~)ЮvйЭyш§yЫ§uзвќзT"йЭyш§yЫ§uзвќзLєw^~)Юt+§uзвќзYєw^~)Юt+§uзвќзUєw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt.

```bash
docker compose logs -f api
docker compose logs -f db
```

йЭyш§yЫ§uзвќзDєw^~)ЮvйЭyш§yЬ єw^~)ЮvйЭyш§yЫ§uзвќз`"йЭyш§yЫ§uзвќзT"йЭyш§yЫ§uзвќзL"йЭyш§yЫ§uзвќзyєw^~)Юt+§uзвќзlєw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt. PostgreSQL+§uзвќзpєw^~)ЮvйЭyш§yР єw^~)ЮvйЭyш§yЫ§uзвќз@"йЭyш§yЫ§uзвќз\єw^~)ЮvйЭyш§yР єw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt.

```bash
docker compose down
```

DBєw^~)ЮvйЭyш§yР єw^~)ЮvйЭyш§yЫ§uзвќзH"йЭyш§yЫ§uзвќзpєw^~)ЮvйЭyш§yР єw^~)ЮvйЭyш§yЬ `-vbйЭyш§yЬ єw^~)ЮvйЭyш§yЫ§uзвќзiєw^~)ЮvйЭyш§yФ.

```bash
docker compose down -v
```
§uзвќзPєw^~)Юt+§uзвќзLєw^~)ЮvйЭyш§yР `data/uploads`,"йЭyш§yЫ§uзвќзXєw^~)ЮvйЭyш§yР `data/processed`, єw^~)ЮvйЭyш§yФ·єw^~)ЮvйЭyш§yШ єw^~)ЮvйЭyш§yЫ§uзвќзpєw^~)ЮvйЭyш§yЫ§uзвќзT PostgreSQL єw^~)ЮvйЭyш§yЫ§uзвќзP"йЭyш§yЫ§uзвќзeєw^~)ЮvйЭyш§yЫ§uзвќзd.

єw^~)ЮvйЭyш§yЬ єw^~)ЮvйЭyш§yЬ єw^~)ЮvйЭyш§yЫ§uзвќзT Linux"йЭyш§yЫ§uзвќзl"йЭyш§yЫ§uзвќзeєw^~)Юt+§uзвќзDєw^~)Юt WSL єw^~)ЮvйЭyш§yР
`/home/daks/projects/picture-rainbйЭyш§yР єw^~)ЮvйЭyш§yЫ§uзвќзHєw^~)Юt.
