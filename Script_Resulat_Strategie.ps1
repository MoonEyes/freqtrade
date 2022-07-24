$file = (Get-content -Path ./pairs.list)
ForEach ($pair in $file) {
	docker-compose run --rm freqtrade backtesting --strategy hibou --timerange 20170410-20220710 --config user_data/config_hibou.json --pairs $pair >> ./resultfor.txt
}
