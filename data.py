

# code: (name, symbol, units per 1 USD -- fixed simulation rates)
CURRENCIES = {
    "USD": ("US Dollar", "$", 1),
    "EUR": ("Euro", "€", 0.92),
    "GBP": ("British Pound", "£", 0.79),
    "NGN": ("Nigerian Naira", "₦", 1500),
    "GHS": ("Ghanaian Cedi", "GH₵", 15),
    "KES": ("Kenyan Shilling", "KSh", 129),
    "ZAR": ("South African Rand", "R", 18),
    "CAD": ("Canadian Dollar", "C$", 1.37),
    "AUD": ("Australian Dollar", "A$", 1.52),
    "NZD": ("New Zealand Dollar", "NZ$", 1.65),
    "INR": ("Indian Rupee", "₹", 84),
    "CNY": ("Chinese Yuan", "¥", 7.2),
    "JPY": ("Japanese Yen", "¥", 150),
    "AED": ("UAE Dirham", "AED", 3.67),
    "SAR": ("Saudi Riyal", "SAR", 3.75),
    "QAR": ("Qatari Riyal", "QAR", 3.64),
    "KWD": ("Kuwaiti Dinar", "KWD", 0.31),
    "EGP": ("Egyptian Pound", "E£", 49),
    "MAD": ("Moroccan Dirham", "MAD", 10),
    "XOF": ("West African CFA Franc", "CFA", 610),
    "XAF": ("Central African CFA Franc", "FCFA", 610),
    "TZS": ("Tanzanian Shilling", "TSh", 2600),
    "UGX": ("Ugandan Shilling", "USh", 3700),
    "RWF": ("Rwandan Franc", "RF", 1350),
    "ETB": ("Ethiopian Birr", "Br", 120),
    "ZMW": ("Zambian Kwacha", "ZK", 27),
    "BWP": ("Botswana Pula", "P", 13.7),
    "BRL": ("Brazilian Real", "R$", 5.5),
    "MXN": ("Mexican Peso", "MX$", 19.5),
    "ARS": ("Argentine Peso", "AR$", 1000),
    "CLP": ("Chilean Peso", "CLP", 950),
    "COP": ("Colombian Peso", "COP", 4100),
    "PEN": ("Peruvian Sol", "S/", 3.8),
    "JMD": ("Jamaican Dollar", "J$", 157),
    "TTD": ("Trinidad & Tobago Dollar", "TT$", 6.8),
    "CHF": ("Swiss Franc", "CHF", 0.88),
    "SEK": ("Swedish Krona", "kr", 10.5),
    "NOK": ("Norwegian Krone", "kr", 10.8),
    "DKK": ("Danish Krone", "kr", 6.9),
    "PLN": ("Polish Zloty", "zł", 4.0),
    "CZK": ("Czech Koruna", "Kč", 23),
    "HUF": ("Hungarian Forint", "Ft", 365),
    "RON": ("Romanian Leu", "lei", 4.6),
    "UAH": ("Ukrainian Hryvnia", "₴", 41),
    "RUB": ("Russian Ruble", "₽", 95),
    "TRY": ("Turkish Lira", "₺", 34),
    "ILS": ("Israeli Shekel", "₪", 3.7),
    "PKR": ("Pakistani Rupee", "Rs", 278),
    "BDT": ("Bangladeshi Taka", "৳", 120),
    "LKR": ("Sri Lankan Rupee", "Rs", 300),
    "IDR": ("Indonesian Rupiah", "Rp", 15800),
    "MYR": ("Malaysian Ringgit", "RM", 4.5),
    "SGD": ("Singapore Dollar", "S$", 1.34),
    "THB": ("Thai Baht", "฿", 35),
    "VND": ("Vietnamese Dong", "₫", 25000),
    "PHP": ("Philippine Peso", "₱", 58),
    "KRW": ("South Korean Won", "₩", 1370),
    "HKD": ("Hong Kong Dollar", "HK$", 7.8),
    "TWD": ("New Taiwan Dollar", "NT$", 32),
}

# name|dial code|default currency
_COUNTRY_TEXT = """
Nigeria|234|NGN
Ghana|233|GHS
Kenya|254|KES
South Africa|27|ZAR
Tanzania|255|TZS
Uganda|256|UGX
Rwanda|250|RWF
Ethiopia|251|ETB
Zambia|260|ZMW
Botswana|267|BWP
Namibia|264|ZAR
Zimbabwe|263|USD
Mozambique|258|USD
Angola|244|USD
Senegal|221|XOF
Côte d'Ivoire|225|XOF
Benin|229|XOF
Togo|228|XOF
Mali|223|XOF
Burkina Faso|226|XOF
Niger|227|XOF
Cameroon|237|XAF
Gabon|241|XAF
Congo|242|XAF
DR Congo|243|USD
Sierra Leone|232|USD
Liberia|231|USD
Gambia|220|USD
Egypt|20|EGP
Morocco|212|MAD
Algeria|213|USD
Tunisia|216|USD
United States|1|USD
Canada|1|CAD
Mexico|52|MXN
Brazil|55|BRL
Argentina|54|ARS
Chile|56|CLP
Colombia|57|COP
Peru|51|PEN
Venezuela|58|USD
Ecuador|593|USD
Uruguay|598|USD
Panama|507|USD
Costa Rica|506|USD
Dominican Republic|1809|USD
Bahamas|1242|USD
Jamaica|1876|JMD
Trinidad and Tobago|1868|TTD
United Kingdom|44|GBP
Ireland|353|EUR
France|33|EUR
Germany|49|EUR
Spain|34|EUR
Italy|39|EUR
Portugal|351|EUR
Netherlands|31|EUR
Belgium|32|EUR
Luxembourg|352|EUR
Austria|43|EUR
Switzerland|41|CHF
Sweden|46|SEK
Norway|47|NOK
Denmark|45|DKK
Finland|358|EUR
Iceland|354|USD
Poland|48|PLN
Czech Republic|420|CZK
Slovakia|421|EUR
Hungary|36|HUF
Romania|40|RON
Bulgaria|359|EUR
Greece|30|EUR
Croatia|385|EUR
Serbia|381|EUR
Slovenia|386|EUR
Lithuania|370|EUR
Latvia|371|EUR
Estonia|372|EUR
Malta|356|EUR
Cyprus|357|EUR
Ukraine|380|UAH
Russia|7|RUB
Turkey|90|TRY
United Arab Emirates|971|AED
Saudi Arabia|966|SAR
Qatar|974|QAR
Kuwait|965|KWD
Bahrain|973|USD
Oman|968|USD
Jordan|962|USD
Lebanon|961|USD
Iraq|964|USD
Israel|972|ILS
India|91|INR
Pakistan|92|PKR
Bangladesh|880|BDT
Sri Lanka|94|LKR
Nepal|977|USD
China|86|CNY
Japan|81|JPY
South Korea|82|KRW
Hong Kong|852|HKD
Taiwan|886|TWD
Singapore|65|SGD
Malaysia|60|MYR
Indonesia|62|IDR
Thailand|66|THB
Vietnam|84|VND
Philippines|63|PHP
Australia|61|AUD
New Zealand|64|NZD
Kazakhstan|7|USD
Other|0|USD
"""

COUNTRIES = []
for _line in _COUNTRY_TEXT.strip().splitlines():
    _n, _d, _c = _line.split("|")
    COUNTRIES.append({"name": _n, "dial": _d, "currency": _c})
COUNTRIES.sort(key=lambda c: (c["name"] == "Other", c["name"]))

ACCOUNT_TYPES = ["Current", "Savings"]

# Fee schedule (percent of amount, with a USD-equivalent floor and ceiling)
FEES = {
    "internal": {"pct": 0.005, "min_usd": 0.10, "max_usd": 5.00},
    "bank": {"pct": 0.010, "min_usd": 0.25, "max_usd": 10.00},
}

CATEGORIES = ["Deposit", "Transfer to", "Transfer from", "Bank Transfer"]
STATUSES = ["Successful", "Pending", "Failed"]

# Principal time zone per country. Only a FALLBACK: the app normally uses the browser's time zone.
COUNTRY_TZ = dict(item.split("=", 1) for item in """Nigeria=Africa/Lagos;Ghana=Africa/Accra;Kenya=Africa/Nairobi;South Africa=Africa/Johannesburg;Tanzania=Africa/Dar_es_Salaam;Uganda=Africa/Kampala;Rwanda=Africa/Kigali;Ethiopia=Africa/Addis_Ababa;Zambia=Africa/Lusaka;Botswana=Africa/Gaborone;Namibia=Africa/Windhoek;Zimbabwe=Africa/Harare;Mozambique=Africa/Maputo;Angola=Africa/Luanda;Senegal=Africa/Dakar;Côte d'Ivoire=Africa/Abidjan;Benin=Africa/Porto-Novo;Togo=Africa/Lome;Mali=Africa/Bamako;Burkina Faso=Africa/Ouagadougou;Niger=Africa/Niamey;Cameroon=Africa/Douala;Gabon=Africa/Libreville;Congo=Africa/Brazzaville;DR Congo=Africa/Kinshasa;Sierra Leone=Africa/Freetown;Liberia=Africa/Monrovia;Gambia=Africa/Banjul;Egypt=Africa/Cairo;Morocco=Africa/Casablanca;Algeria=Africa/Algiers;Tunisia=Africa/Tunis;United States=America/New_York;Canada=America/Toronto;Mexico=America/Mexico_City;Brazil=America/Sao_Paulo;Argentina=America/Argentina/Buenos_Aires;Chile=America/Santiago;Colombia=America/Bogota;Peru=America/Lima;Venezuela=America/Caracas;Ecuador=America/Guayaquil;Uruguay=America/Montevideo;Panama=America/Panama;Costa Rica=America/Costa_Rica;Dominican Republic=America/Santo_Domingo;Bahamas=America/Nassau;Jamaica=America/Jamaica;Trinidad and Tobago=America/Port_of_Spain;United Kingdom=Europe/London;Ireland=Europe/Dublin;France=Europe/Paris;Germany=Europe/Berlin;Spain=Europe/Madrid;Italy=Europe/Rome;Portugal=Europe/Lisbon;Netherlands=Europe/Amsterdam;Belgium=Europe/Brussels;Luxembourg=Europe/Luxembourg;Austria=Europe/Vienna;Switzerland=Europe/Zurich;Sweden=Europe/Stockholm;Norway=Europe/Oslo;Denmark=Europe/Copenhagen;Finland=Europe/Helsinki;Iceland=Atlantic/Reykjavik;Poland=Europe/Warsaw;Czech Republic=Europe/Prague;Slovakia=Europe/Bratislava;Hungary=Europe/Budapest;Romania=Europe/Bucharest;Bulgaria=Europe/Sofia;Greece=Europe/Athens;Croatia=Europe/Zagreb;Serbia=Europe/Belgrade;Slovenia=Europe/Ljubljana;Lithuania=Europe/Vilnius;Latvia=Europe/Riga;Estonia=Europe/Tallinn;Malta=Europe/Malta;Cyprus=Asia/Nicosia;Ukraine=Europe/Kyiv;Russia=Europe/Moscow;Turkey=Europe/Istanbul;United Arab Emirates=Asia/Dubai;Saudi Arabia=Asia/Riyadh;Qatar=Asia/Qatar;Kuwait=Asia/Kuwait;Bahrain=Asia/Bahrain;Oman=Asia/Muscat;Jordan=Asia/Amman;Lebanon=Asia/Beirut;Iraq=Asia/Baghdad;Israel=Asia/Jerusalem;India=Asia/Kolkata;Pakistan=Asia/Karachi;Bangladesh=Asia/Dhaka;Sri Lanka=Asia/Colombo;Nepal=Asia/Kathmandu;China=Asia/Shanghai;Japan=Asia/Tokyo;South Korea=Asia/Seoul;Hong Kong=Asia/Hong_Kong;Taiwan=Asia/Taipei;Singapore=Asia/Singapore;Malaysia=Asia/Kuala_Lumpur;Indonesia=Asia/Jakarta;Thailand=Asia/Bangkok;Vietnam=Asia/Ho_Chi_Minh;Philippines=Asia/Manila;Australia=Australia/Sydney;New Zealand=Pacific/Auckland;Kazakhstan=Asia/Almaty;Other=UTC""".split(";"))
