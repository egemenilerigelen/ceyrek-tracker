# Çeyrek Takip

Ekranın sağ kenarından kayarak açılan, modüler bir Windows durum paneli. Her bilgi
(hava durumu, sistem, piyasa, müzik...) bağımsız bir **kart**tır; kartlar açılıp
kapanabilir, katlanabilir ve sıralanabilir.

<p>
  <img src="docs/panel.png" alt="Panel: üst bilgi satırı, hava durumu ve finans kartları" width="340">
</p>

> Proje geliştirme aşamasında. Şu an panel iskeleti, tema katmanı, üst bilgi satırı ve
> **hava durumu**, **finans** (döviz, altın), **telemetri**, **Spotify**, **pano** ve **GitHub**
> kartları çalışıyor. Takvim ve pil/ses kartları sırayla eklenecek.

## Kullanım

- **Açmak:** sağ kenardaki ince tutamacın üzerine gel (varsayılan 200 ms bekler) ya da
  tıkla. `Win+Alt+P` kısayolu ve tepsi ikonu da paneli açıp kapatır.
- **Kapatmak:** panelin dışına tıkla ya da fareyi panelden 3 sn uzak tut. Kısayol ve tepsi
  ikonu her zaman kapatır.
- **Sabitlemek:** üst satırdaki iğne düğmesi paneli açık tutar; dışarı tıklama ve fare
  ayrılması kapatmaz. Durum hatırlanır.
- **Katlamak:** kart başlığına tıkla; durum hatırlanır.

## Ayarlar

Tek dosya: `%APPDATA%\CeyrekTakip\settings.json` (uygulama kapalıyken düzenle; hatalı
değerler sessizce varsayılana döner). Ayarlar ekranı sonraki aşamada gelecek.

| Alan | Anlamı |
| --- | --- |
| `open_mode` | `hover` (üzerine gelince) ya da `click` (yalnızca tıklayınca) |
| `hover_delay_ms`, `leave_close_seconds` | Açılış gecikmesi, fare ayrılınca kapanma süresi (0 = kapalı) |
| `hotkey`, `hotkey_screen` | Kısayol (boş = yok) ve hangi ekranda açılacağı (`cursor` / `primary`) |
| `trigger_screen` | Tutamacın ekranı: `primary` ya da ekran adı (ör. `\\.\DISPLAY2`) |
| `handle_thickness`, `handle_length`, `handle_position` | Tutamacın boyutu ve dikey konumu (0 üst, 1 alt) |
| `theme`, `accent`, `density`, `font_scale` | `dark`/`light`, `#rrggbb` vurgu, `compact`/`normal`/`relaxed`, yazı ölçeği |
| `glass_opacity`, `animations`, `animation_ms` | Panel zemininin opaklığı (0,3–1; varsayılan 0,92, düşürdükçe arkadaki pencereler daha çok görünür) ve animasyonlar |
| `cards` | Her kart için `enabled`, `collapsed` ve `config` (ör. hava için `{"city": "Ankara"}`, finans için `{"items": ["usd", "eur", "ceyrek"]}`) |

`Win+Alt+W` gibi bazı kısayollar başka uygulamalarca tutulmuş olabilir; kayıt başarısız
olursa tepsiden uyarı gelir ve `hotkey` değiştirilebilir.

### Finans kartı

Dolar, euro, sterlin, gram altın ve çeyrek altın satış fiyatlarını (ve
günlük değişimi) yalnızca yazı olarak gösterir. Veri, panel açıkken dakikada bir
Truncgil'den çekilir; ulaşılamazsa Altınkaynak denenir. Başlıktaki bilgi normalde boştur;
yalnızca yedek kaynak devredeyse kaynağın adı (fiyatlar kaynağa göre değişir), veri 15
dakikadan eskiyse (hafta sonu, kapalı piyasa) saati, güncelleme başarısızsa "eski veri"
notu yazar.

Gösterilecek satırlar `cards` içindeki `finance` ayarında `items` ile seçilir (sıra
korunur): `usd`, `eur`, `gbp`, `chf`, `gram`, `gram_has`, `ceyrek`, `yarim`, `tam`,
`cumhuriyet`, `ata`, `resat`, `hamit`, `ikibucuk`, `gremse`, `besli`, `ayar14`, `ayar18`,
`bilezik22`, `ons`, `gumus`. Ons ve gümüş varsayılanda gösterilmez, `items` ile eklenir.
Altınkaynak'ta karşılığı olmayan satırlar (ör. `cumhuriyet`) o kaynağa düşülünce `—`
görünür.

### Spotify kartı

Spotify masaüstü uygulamasında çalan şarkıyı gösterir ve yönetir: kapak, şarkı, sanatçı,
ilerleme çubuğu (istediğin yere tıklayıp atlanır), önceki / oynat-duraklat /
sonraki, karıştır, tekrarla, ses düzeyi ve ses çıkışı. Hesap bağlamak gerekmez; veri
Windows'un medya oturumundan gelir, bu yüzden yalnızca Spotify'ı izler (tarayıcı
sekmelerini ya da başka çalarları değil) ve Premium şartı yoktur. Panel açıkken saniyede
bir okunur.

- **Spotify kapalıyken** en son kalan şarkı (kapağı ve konumuyla) görünür; uygulama
  Spotify kapalıyken açılsa da böyle olur. Oynat/atla düğmeleri pasifleşir; Spotify açılınca
  güncel şarkı gelir.
- **Kapak** yalnızca albüm görselidir; Spotify'ın görsele eklediği logo bandı kırpılır.
- **Renkler kapağı izler:** kartın arka planındaki yumuşak ışık kapağın baskın tonunu yansıtır;
  şarkı çubuğu, açık karıştır/tekrarla düğmeleri ve oynat dolgusu da aynı tonu alır. Renk,
  algısal OKLCH uzayında seçilir: siyah, beyaz ve gri alanlar oy kullanmaz, her kapakta ışıma
  eşit güçte görünür, çubuk gerçek zemininde okunur kalır. Gri kapağa renk uydurulmaz. Kapak
  yoksa temanın vurgu rengi (altın) kalır.
- **Arka plan panele oturur:** kartın ayrı bir açık yüzeyi yoktur, panelin zemini doğrudan
  görünür. Üzerine, kapaktan uzaklaştıkça irileşen dalgalı bir nokta deseni çok hafifçe biner.
- **Oynat düğmesi** çalarken sade (yalnızca duraklat simgesi), duraklayınca soluk dolgulu
  görünür.
- **Katlıyken** başlık satırında "Sanatçı – Şarkı" özeti görünür.
- **Ses çubuğu** Windows'un sistem sesini (görev çubuğundaki hoparlör) ayarlar; Spotify
  kapalıyken de çalışır. Spotify'ın uygulama içi ses çubuğu dışarıdan ayarlanamaz.
- **Çıkış cihazı** düğmesi, bağlı hoparlör ve kulaklıkları listeler; seçilen, Windows'un
  **varsayılan** çıkışı olur (yalnızca Spotify'ı değil tüm sistemi etkiler).
- Reklam sırasında Spotify atlamayı ve şarkı geçmeyi kapatır; düğmeler de pasif görünür.

### Telemetri kartı

İşlemci, bellek, ekran kartı ve ağın canlı durumunu gösterir. Her satır tek satırdır: simge ve ad,
sönük kısa bir ayrıntı (ör. `4,68 GHz`), çizgi grafik ya da doluluk çubuğu ve renkli bir değer.
Satırın üzerine gelince tam bilgi ipucunda görünür (ör. `Ryzen 5 7500F · 4,68 GHz`). Veri panel açıkken saniyede bir okunur; panel kapanınca ya da
kart katlanınca okuma durur.

| Satır (`items` adı) | Ayrıntı (ipucunda tamamı) | Değer |
| --- | --- | --- |
| İşlemci (`cpu`) | model · saat hızı | kullanım % |
| Bellek (`ram`) | kullanılan / toplam | doluluk % |
| Ekran Kartı (`gpu`) | model · sıcaklık | kullanım % |
| Video Belleği (`vram`) | kullanılan / toplam | doluluk % |
| GPU Güç (`gpu_power`) | çekirdek hızı · fan | çekilen güç (W); çubuk güç sınırına oranı |
| Ağ (`net`) | ↓ indirme ↑ yükleme (bit/sn) | ping (ms); grafik pingin geçmişi |

- **Renkler:** her satırın kendi tonu vardır; doluluk %75'i geçince değer ve grafik turuncuya,
  %90'ı geçince kırmızıya döner. Ping 100 ms'den sonra turuncu, 250 ms'den sonra (ya da yanıt
  yoksa) kırmızıdır. Tonlar `theme/tokens.py` içinde, açık ve koyu tema için ayrı tanımlıdır.
- **Ekran kartı** yalnızca NVIDIA'dan (sürücüyle gelen NVML) okunur. NVIDIA kartı ya da sürücüsü
  yoksa üç GPU satırı hiç görünmez; kartın fan ya da güç bilgisi vermeyen bir modeli için yalnızca
  o veri atlanır.
- **Ping,** `1.1.1.1:443` adresine TCP bağlantısı kurma süresidir (ICMP yetki ister); sistem
  okumalarından ayrı çalışır, yanıt gelmezse diğer değerler gecikmez.
- **Satırları seçmek:** `cards` içindeki `telemetry` ayarında `items` ile (sıra korunur),
  ör. `{"items": ["cpu", "ram", "net"]}`. Kaldırılan disk satırları (`disk_io`, `drives`) eski
  ayar dosyalarında kalsa da yok sayılır.

### Pano kartı

Son 5 kopyalanan metni, en yenisi üstte, listeler. Satırın herhangi bir yerine tıklamak
(başındaki kopyalama simgesi dahil) metni panoya geri koyar (bir an onay işareti görünür) ve
satırı en üste taşır; aynı metin tekrar kopyalanırsa ikinci satır açılmaz, var olan satır
yukarı çıkar. Fare satırın üzerindeyken sağda sönük bir çarpı belirir; çarpının üstüne gelince
aydınlanır, tıklayınca satır geçmişten silinir (panodaki metne dokunmaz).

- **Panel kapalıyken de kopyalananlar yakalanır:** kart panoyu olay olarak dinler, yoklama
  yoktur, boşta işlemci kullanmaz. Uygulama açılırken panoda duran metin de listelenir.
- **Yalnızca metin:** resimler ve Explorer'da kopyalanan dosyalar listeye girmez; tarayıcıdan
  kopyalanan bağlantı metindir, girer.
- **Parolalar atlanır:** parola yöneticilerinin panoya koyarken ekledikleri "geçmişe alma"
  işaretini taşıyan içerik listeye hiç girmez.
- **Satırlar tek satıra indirilir:** çok satırlı metin boşluklarla birleşik gösterilir,
  sığmayan kısım `…` ile kesilir (üzerine gelince tamamı görünür). Kopyalanan metin değişmez,
  satır sonlarıyla olduğu gibi geri gelir.
- **Geçmiş diske yazılmaz:** yalnızca bellektedir; uygulama kapanınca silinir. Pano parola ya da
  gizli bilgi taşıyabileceği için bilerek böyle.

### GitHub kartı

GitHub katkı tablosunu gösterir: panele sığan en yeni haftalar, pazartesi üstte olacak şekilde
kare kare; yeni hafta sağ kenardadır. Karenin üzerine gelince katkı sayısı ve tarih ipucunda
görünür. Altında son bir yılın toplam katkısı (GitHub profilindeki sayıyla aynıdır) ve bugünde
biten seri yazar; bugün henüz katkı yoksa seri bozulmuş sayılmaz, dünden geriye sayılır.

- **Hesap ya da token gerekmez:** veri, kullanıcının herkese açık profil sayfasındaki katkı
  parçasından okunur (`github.com/users/<ad>/contributions`). Özel depo katkıları, profilinde
  "Private contributions" açık değilse görünmez.
- **Kullanıcı adı:** `cards` içindeki `github` ayarında `username` ile verilir (varsayılan
  `egemenilerigelen`), ör. `{"username": "octocat"}`. Yenileme aralığı `refresh_minutes` ile
  (5–720, varsayılan 30) değişir. Katkılar yavaş değiştiği için panel kapalıyken de seyrek yenilenir.
- **Renkler:** karelerin tonu GitHub'ın kendi 0–4 yoğunluk basamağını izler ve temanın vurgu
  rengini kullanır (`accent` ile değişir); katkısız günler soluk bir iz rengindedir.
- **Resmi API değil:** GitHub sayfa yapısını değiştirirse okuma başarısız olur; kart son tabloyu
  başlıkta "eski veri" notuyla göstermeye devam eder, hiç veri yoksa kartta hata yazar.

## Kurulum ve çalıştırma

Python 3.11 veya üstü gerekir.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
ceyrek-takip            # ya da: python -m ceyrek_tracker / python main.py
```

## Geliştirme

```bash
python -m pytest -q          # testler (Qt testleri ekransız çalışır)
python -m ruff check .       # lint
python -m ruff format .      # biçimlendirme
python -m PyInstaller --noconfirm CeyrekTakip.spec   # dist\CeyrekTakip.exe
```

## Mimari

Bağımlılık yalnızca aşağıya doğru akar; kurallar `tests/test_architecture.py` ile her test
çalışmasında denetlenir.

```text
app  ->  cards/<özellik>  ->  core  ->  infra, theme
```

```text
src/ceyrek_tracker/
├── app.py            # birleştirme noktası: AppController + giriş noktası (her şeyi bilen tek yer)
├── core/             # panel iskeleti; hiçbir karta bağımlı değil
│   ├── settings.py       # ayarlar (settings.json) ve görünüm üretimi
│   ├── panel_window.py   # çerçevesiz yüzen panel, kayma animasyonu
│   ├── panel_surface.py  # yarı saydam, yuvarlak köşeli, dokulu panel zemini (Qt ile çizilir)
│   ├── card_base.py · card_host.py · card_manager.py   # kart arayüzü, çerçevesi, yaşam döngüsü
│   ├── auto_close.py     # dışarı tıklama / fare uzaklaşması kararı (fare ve saat enjekte edilir)
│   ├── tray.py · header.py · polling.py · widgets.py · screens.py · turkish.py
│   ├── trigger/          # tetikleyici arayüzü + tutamaç (kolay değişir)
│   └── platform/         # Windows'a özgü: hotkey, single_instance, mouse, appid
├── cards/            # her kart kendi paketi; kartlar birbirini bilmez
│   ├── __init__.py       # kart kayıt defteri (CARDS)
│   ├── weather/          # card · api · cache · places · icon · backdrop
│   ├── finance/          # card · catalog · models · providers · service · cache · formatting
│   ├── telemetry/        # card · sampler (psutil) · gpu (NVML) · ping · widgets (grafikler) · icon · formatting · windows · models
│   ├── spotify/          # card · backend · windows (WinRT + pycaw) · worker · palette · backdrop · logo · cache · models · widgets · formatting
│   ├── clipboard/        # card · history
│   └── github/           # card · api (profil sayfası ayrıştırıcı) · cache · models · widgets (ızgara) · icon
├── theme/            # tüm renk, boyut, yazı tipi: tokens.py (tek yer) + stil sayfası
└── infra/            # kaynaktan bağımsız altyapı: paths · storage · http · logging_setup
```

- **Yeni kart eklemek:** `cards/<ad>/` paketi aç, `Card` türeten sınıfı yaz, `__init__.py`
  içinde bir `SPEC` (`CardSpec`) dışa aktar ve `cards/__init__.py` içindeki `CARDS` listesine
  ekle. Kartın önbellek dosyası ve verisi kendi paketinde kalır; `core` ve `infra`
  dışında hiçbir şeye bağımlı olamaz (başka karta bile).
- **Hata dayanıklılığı:** Bir kart kurulurken, güncellenirken ya da sinyal işlerken hata
  verirse yalnızca o kartta mesaj görünür; panel ve diğer kartlar etkilenmez.
- **Test edilebilirlik:** Fare, saat, önbellek ve HTTP gibi dış bağımlılıklar kurucudan
  (constructor) verilir; testler gerçek sisteme dokunmaz.
- **Performans:** Panel kapalıyken kartların zamanlayıcıları durur (`on_hide`), fare
  izleme zamanlayıcısı yalnızca panel açıkken çalışır. Boşta CPU %0 civarındadır.
- **Görünümü değiştirmek:** `theme/tokens.py` içindeki `DARK` / `LIGHT` ön ayarları ve
  `Metrics` (yoğunluk, yazı ölçeği) tek yerdir; kartlarda sabit renk yoktur.

## Kullanıcı verisi

`%APPDATA%\CeyrekTakip\` klasöründe tutulur:

- `settings.json`: ayarlar
- `weather.json`: son hava durumu yanıtı (internet yokken eski veriyi göstermek için)
- `last_snapshot.json`: son finans fiyatları (aynı amaçla)
- `spotify.json`, `spotify_cover.bin`: en son çalan şarkı ve kapağı (Spotify kapalıyken gösterilir)
- `github.json`: son katkı tablosu (internet yokken eski tabloyu göstermek için)
- `logs\app.log`: loglar (sorun bildirirken bu dosyayı ekleyin)
