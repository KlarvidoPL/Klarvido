import { Locale } from '@sb/webapp-core/config/i18n';

// Keyed by locale rather than run through intl.formatMessage(): ICU MessageFormat
// parsing collapses blank lines, which silently destroys markdown's block structure
// (headings/paragraphs/lists all merge into one block) - fine for short UI strings,
// not for multi-paragraph content like this. See staticContentPage.component.tsx.
export const privacyPolicyContent: Partial<Record<Locale, string>> = {
  [Locale.ENGLISH]: `
## 1. Introduction

This Privacy Policy explains how Klarvido collects, uses, discloses, and safeguards your information when you use our service. Please read this privacy policy carefully.

## 2. Information We Collect

### 2.1 Personal Data
We may collect personally identifiable information, including but not limited to:
- Name and email address
- Phone number
- Billing and payment information
- Usage data and preferences

### 2.2 Automatically Collected Information
When you access our service, we automatically collect:
- Device and browser information
- IP address and location data
- Usage patterns and preferences
- Cookies and similar tracking technologies

## 3. How We Use Your Information

We use the information we collect to:
1. Provide and maintain our service
2. Process transactions and send related information
3. Send promotional communications (with your consent)
4. Respond to your inquiries and support requests
5. Improve our services and user experience
6. Comply with legal obligations

## 4. Data Sharing and Disclosure

We may share your information with:
- **Service Providers**: Third parties that help us operate our service
- **Business Partners**: For joint marketing or service offerings
- **Legal Compliance**: When required by law or to protect our rights

We do not sell your personal information to third parties.

## 5. Data Security

We implement appropriate technical and organizational measures to protect your data, including:
- Encryption of data in transit and at rest
- Regular security assessments
- Access controls and authentication
- Employee training on data protection

## 6. Your Rights

Depending on your location, you may have the right to:
- Access your personal data
- Correct inaccurate data
- Delete your data
- Object to processing
- Data portability
- Withdraw consent

## 7. Cookies and Tracking

We use cookies and similar technologies to:
- Remember your preferences
- Analyze usage patterns
- Provide personalized content
- Improve our services

You can control cookies through your browser settings.

## 8. Children's Privacy

Our service is not intended for children under 13. We do not knowingly collect information from children under 13.

## 9. Changes to This Policy

We may update this Privacy Policy from time to time. We will notify you of any changes by posting the new policy on this page and updating the "Last Updated" date.

## 10. Contact Us

If you have questions about this Privacy Policy, please contact us at privacy@klarvido.com.

---

*This is placeholder content and has not been reviewed by legal counsel. Replace it with your finalized Privacy Policy before relying on it.*
`,
  [Locale.POLISH]: `
## 1. Wprowadzenie

Niniejsza Polityka prywatności wyjaśnia, w jaki sposób Klarvido gromadzi, wykorzystuje, ujawnia i chroni Twoje dane podczas korzystania z naszej usługi. Prosimy o uważne zapoznanie się z niniejszą polityką prywatności.

## 2. Informacje, które gromadzimy

### 2.1 Dane osobowe
Możemy gromadzić dane umożliwiające identyfikację osoby, w tym między innymi:
- Imię i nazwisko oraz adres e-mail
- Numer telefonu
- Informacje dotyczące płatności i rozliczeń
- Dane dotyczące użytkowania i preferencji

### 2.2 Informacje zbierane automatycznie
Podczas korzystania z naszej usługi automatycznie zbieramy:
- Informacje o urządzeniu i przeglądarce
- Adres IP i dane o lokalizacji
- Wzorce użytkowania i preferencje
- Pliki cookie i podobne technologie śledzące

## 3. Jak wykorzystujemy Twoje informacje

Wykorzystujemy zebrane informacje, aby:
1. Świadczyć i utrzymywać naszą usługę
2. Przetwarzać transakcje i wysyłać powiązane informacje
3. Wysyłać komunikaty promocyjne (za Twoją zgodą)
4. Odpowiadać na Twoje zapytania i prośby o wsparcie
5. Ulepszać nasze usługi i doświadczenie użytkownika
6. Wypełniać obowiązki prawne

## 4. Udostępnianie i ujawnianie danych

Możemy udostępniać Twoje dane:
- **Dostawcom usług**: podmiotom trzecim, które pomagają nam obsługiwać naszą usługę
- **Partnerom biznesowym**: w celu wspólnych działań marketingowych lub ofert usług
- **Zgodności z prawem**: gdy wymaga tego prawo lub w celu ochrony naszych praw

Nie sprzedajemy Twoich danych osobowych stronom trzecim.

## 5. Bezpieczeństwo danych

Wdrażamy odpowiednie środki techniczne i organizacyjne w celu ochrony Twoich danych, w tym:
- Szyfrowanie danych podczas przesyłania i przechowywania
- Regularne oceny bezpieczeństwa
- Kontrolę dostępu i uwierzytelnianie
- Szkolenia pracowników z zakresu ochrony danych

## 6. Twoje prawa

W zależności od Twojej lokalizacji możesz mieć prawo do:
- Dostępu do swoich danych osobowych
- Poprawiania nieprawidłowych danych
- Usunięcia swoich danych
- Sprzeciwu wobec przetwarzania
- Przenoszenia danych
- Wycofania zgody

## 7. Pliki cookie i śledzenie

Wykorzystujemy pliki cookie i podobne technologie, aby:
- Zapamiętywać Twoje preferencje
- Analizować wzorce użytkowania
- Dostarczać spersonalizowane treści
- Ulepszać nasze usługi

Możesz kontrolować pliki cookie za pomocą ustawień przeglądarki.

## 8. Prywatność dzieci

Nasza usługa nie jest przeznaczona dla dzieci poniżej 13 roku życia. Świadomie nie gromadzimy danych od dzieci poniżej 13 roku życia.

## 9. Zmiany w niniejszej Polityce

Możemy okresowo aktualizować niniejszą Politykę prywatności. Powiadomimy Cię o wszelkich zmianach, publikując nową politykę na tej stronie i aktualizując datę „Ostatnia aktualizacja".

## 10. Kontakt

Jeśli masz pytania dotyczące niniejszej Polityki prywatności, skontaktuj się z nami pod adresem privacy@klarvido.com.

---

*Jest to treść zastępcza, która nie została zweryfikowana przez prawnika. Przed poleganiem na niej zastąp ją finalną wersją Polityki prywatności.*
`,
  [Locale.GERMAN]: `
## 1. Einleitung

Diese Datenschutzrichtlinie erläutert, wie Klarvido Ihre Informationen bei der Nutzung unseres Dienstes erhebt, verwendet, offenlegt und schützt. Bitte lesen Sie diese Datenschutzrichtlinie sorgfältig durch.

## 2. Informationen, die wir erheben

### 2.1 Personenbezogene Daten
Wir können personenbezogene Daten erheben, einschließlich, aber nicht beschränkt auf:
- Name und E-Mail-Adresse
- Telefonnummer
- Abrechnungs- und Zahlungsinformationen
- Nutzungsdaten und Präferenzen

### 2.2 Automatisch erhobene Informationen
Wenn Sie auf unseren Dienst zugreifen, erheben wir automatisch:
- Geräte- und Browserinformationen
- IP-Adresse und Standortdaten
- Nutzungsmuster und Präferenzen
- Cookies und ähnliche Tracking-Technologien

## 3. Wie wir Ihre Informationen verwenden

Wir verwenden die erhobenen Informationen, um:
1. Unseren Dienst bereitzustellen und aufrechtzuerhalten
2. Transaktionen zu verarbeiten und zugehörige Informationen zu senden
3. Werbliche Mitteilungen zu senden (mit Ihrer Zustimmung)
4. Auf Ihre Anfragen und Support-Anliegen zu reagieren
5. Unsere Dienste und die Nutzererfahrung zu verbessern
6. Rechtlichen Verpflichtungen nachzukommen

## 4. Datenweitergabe und -offenlegung

Wir können Ihre Informationen weitergeben an:
- **Dienstleister**: Dritte, die uns bei der Bereitstellung unseres Dienstes unterstützen
- **Geschäftspartner**: für gemeinsame Marketing- oder Serviceangebote
- **Rechtliche Compliance**: wenn gesetzlich vorgeschrieben oder zum Schutz unserer Rechte

Wir verkaufen Ihre persönlichen Daten nicht an Dritte.

## 5. Datensicherheit

Wir setzen angemessene technische und organisatorische Maßnahmen zum Schutz Ihrer Daten ein, einschließlich:
- Verschlüsselung von Daten während der Übertragung und Speicherung
- Regelmäßige Sicherheitsbewertungen
- Zugriffskontrollen und Authentifizierung
- Mitarbeiterschulungen zum Datenschutz

## 6. Ihre Rechte

Je nach Ihrem Standort haben Sie möglicherweise das Recht:
- Auf Ihre personenbezogenen Daten zuzugreifen
- Unrichtige Daten zu berichtigen
- Ihre Daten zu löschen
- Der Verarbeitung zu widersprechen
- Auf Datenübertragbarkeit
- Ihre Einwilligung zu widerrufen

## 7. Cookies und Tracking

Wir verwenden Cookies und ähnliche Technologien, um:
- Ihre Präferenzen zu speichern
- Nutzungsmuster zu analysieren
- Personalisierte Inhalte bereitzustellen
- Unsere Dienste zu verbessern

Sie können Cookies über Ihre Browsereinstellungen steuern.

## 8. Datenschutz für Kinder

Unser Dienst ist nicht für Kinder unter 13 Jahren bestimmt. Wir erheben wissentlich keine Informationen von Kindern unter 13 Jahren.

## 9. Änderungen dieser Richtlinie

Wir können diese Datenschutzrichtlinie von Zeit zu Zeit aktualisieren. Wir werden Sie über Änderungen informieren, indem wir die neue Richtlinie auf dieser Seite veröffentlichen und das Datum „Zuletzt aktualisiert" ändern.

## 10. Kontakt

Wenn Sie Fragen zu dieser Datenschutzrichtlinie haben, kontaktieren Sie uns bitte unter privacy@klarvido.com.

---

*Dies ist ein Platzhaltertext, der nicht von einem Rechtsberater geprüft wurde. Ersetzen Sie ihn durch Ihre endgültige Datenschutzrichtlinie, bevor Sie sich darauf verlassen.*
`,
  [Locale.SPANISH]: `
## 1. Introducción

Esta Política de Privacidad explica cómo Klarvido recopila, utiliza, divulga y protege tu información cuando utilizas nuestro servicio. Lee atentamente esta política de privacidad.

## 2. Información que recopilamos

### 2.1 Datos personales
Podemos recopilar información de identificación personal, incluyendo, entre otros:
- Nombre y dirección de correo electrónico
- Número de teléfono
- Información de facturación y pago
- Datos de uso y preferencias

### 2.2 Información recopilada automáticamente
Cuando accedes a nuestro servicio, recopilamos automáticamente:
- Información del dispositivo y del navegador
- Dirección IP y datos de ubicación
- Patrones de uso y preferencias
- Cookies y tecnologías de seguimiento similares

## 3. Cómo utilizamos tu información

Utilizamos la información que recopilamos para:
1. Proporcionar y mantener nuestro servicio
2. Procesar transacciones y enviar información relacionada
3. Enviar comunicaciones promocionales (con tu consentimiento)
4. Responder a tus consultas y solicitudes de soporte
5. Mejorar nuestros servicios y la experiencia del usuario
6. Cumplir con las obligaciones legales

## 4. Intercambio y divulgación de datos

Podemos compartir tu información con:
- **Proveedores de servicios**: terceros que nos ayudan a operar nuestro servicio
- **Socios comerciales**: para marketing conjunto u ofertas de servicios
- **Cumplimiento legal**: cuando lo exija la ley o para proteger nuestros derechos

No vendemos tu información personal a terceros.

## 5. Seguridad de los datos

Implementamos medidas técnicas y organizativas adecuadas para proteger tus datos, entre ellas:
- Cifrado de datos en tránsito y en reposo
- Evaluaciones de seguridad periódicas
- Controles de acceso y autenticación
- Formación del personal en protección de datos

## 6. Tus derechos

Según tu ubicación, puedes tener derecho a:
- Acceder a tus datos personales
- Corregir datos inexactos
- Eliminar tus datos
- Oponerte al tratamiento
- La portabilidad de los datos
- Retirar tu consentimiento

## 7. Cookies y seguimiento

Utilizamos cookies y tecnologías similares para:
- Recordar tus preferencias
- Analizar patrones de uso
- Proporcionar contenido personalizado
- Mejorar nuestros servicios

Puedes controlar las cookies a través de la configuración de tu navegador.

## 8. Privacidad de los menores

Nuestro servicio no está dirigido a menores de 13 años. No recopilamos conscientemente información de menores de 13 años.

## 9. Cambios en esta política

Es posible que actualicemos esta Política de Privacidad periódicamente. Te notificaremos cualquier cambio publicando la nueva política en esta página y actualizando la fecha de "Última actualización".

## 10. Contáctanos

Si tienes preguntas sobre esta Política de Privacidad, contáctanos en privacy@klarvido.com.

---

*Este es contenido de marcador de posición que no ha sido revisado por un asesor legal. Reemplázalo con tu Política de Privacidad definitiva antes de basarte en él.*
`,
  [Locale.FRENCH]: `
## 1. Introduction

Cette Politique de Confidentialité explique comment Klarvido collecte, utilise, divulgue et protège vos informations lorsque vous utilisez notre service. Veuillez lire attentivement cette politique de confidentialité.

## 2. Informations que nous collectons

### 2.1 Données personnelles
Nous pouvons collecter des informations personnelles identifiables, notamment :
- Nom et adresse e-mail
- Numéro de téléphone
- Informations de facturation et de paiement
- Données d'utilisation et préférences

### 2.2 Informations collectées automatiquement
Lorsque vous accédez à notre service, nous collectons automatiquement :
- Informations sur l'appareil et le navigateur
- Adresse IP et données de localisation
- Habitudes d'utilisation et préférences
- Cookies et technologies de suivi similaires

## 3. Comment nous utilisons vos informations

Nous utilisons les informations collectées pour :
1. Fournir et maintenir notre service
2. Traiter les transactions et envoyer les informations associées
3. Envoyer des communications promotionnelles (avec votre consentement)
4. Répondre à vos demandes et requêtes d'assistance
5. Améliorer nos services et l'expérience utilisateur
6. Se conformer aux obligations légales

## 4. Partage et divulgation des données

Nous pouvons partager vos informations avec :
- **Prestataires de services** : des tiers qui nous aident à exploiter notre service
- **Partenaires commerciaux** : pour des offres marketing ou de services conjointes
- **Conformité légale** : lorsque la loi l'exige ou pour protéger nos droits

Nous ne vendons pas vos informations personnelles à des tiers.

## 5. Sécurité des données

Nous mettons en œuvre des mesures techniques et organisationnelles appropriées pour protéger vos données, notamment :
- Le chiffrement des données en transit et au repos
- Des évaluations de sécurité régulières
- Des contrôles d'accès et une authentification
- La formation des employés à la protection des données

## 6. Vos droits

Selon votre localisation, vous pouvez avoir le droit de :
- Accéder à vos données personnelles
- Corriger des données inexactes
- Supprimer vos données
- Vous opposer au traitement
- La portabilité des données
- Retirer votre consentement

## 7. Cookies et suivi

Nous utilisons des cookies et des technologies similaires pour :
- Mémoriser vos préférences
- Analyser les habitudes d'utilisation
- Fournir du contenu personnalisé
- Améliorer nos services

Vous pouvez contrôler les cookies via les paramètres de votre navigateur.

## 8. Confidentialité des enfants

Notre service n'est pas destiné aux enfants de moins de 13 ans. Nous ne collectons pas sciemment d'informations auprès d'enfants de moins de 13 ans.

## 9. Modifications de cette politique

Nous pouvons mettre à jour cette Politique de Confidentialité de temps à autre. Nous vous informerons de tout changement en publiant la nouvelle politique sur cette page et en mettant à jour la date de « Dernière mise à jour ».

## 10. Nous contacter

Si vous avez des questions concernant cette Politique de Confidentialité, veuillez nous contacter à privacy@klarvido.com.

---

*Il s'agit d'un contenu provisoire qui n'a pas été examiné par un conseiller juridique. Remplacez-le par votre Politique de Confidentialité définitive avant de vous y fier.*
`,
  [Locale.HINDI]: `
## 1. परिचय

यह गोपनीयता नीति बताती है कि जब आप हमारी सेवा का उपयोग करते हैं तो Klarvido आपकी जानकारी कैसे एकत्र, उपयोग, प्रकट और सुरक्षित करता है। कृपया इस गोपनीयता नीति को ध्यानपूर्वक पढ़ें।

## 2. हम कौन सी जानकारी एकत्र करते हैं

### 2.1 व्यक्तिगत डेटा
हम व्यक्तिगत रूप से पहचान योग्य जानकारी एकत्र कर सकते हैं, जिसमें शामिल हैं परंतु इन्हीं तक सीमित नहीं:
- नाम और ईमेल पता
- फ़ोन नंबर
- बिलिंग और भुगतान जानकारी
- उपयोग डेटा और प्राथमिकताएँ

### 2.2 स्वचालित रूप से एकत्रित जानकारी
जब आप हमारी सेवा तक पहुँचते हैं, तो हम स्वचालित रूप से एकत्र करते हैं:
- डिवाइस और ब्राउज़र जानकारी
- IP पता और स्थान डेटा
- उपयोग पैटर्न और प्राथमिकताएँ
- कुकीज़ और समान ट्रैकिंग तकनीकें

## 3. हम आपकी जानकारी का उपयोग कैसे करते हैं

हम एकत्र की गई जानकारी का उपयोग निम्नलिखित के लिए करते हैं:
1. हमारी सेवा प्रदान करना और बनाए रखना
2. लेन-देन संसाधित करना और संबंधित जानकारी भेजना
3. प्रचार संचार भेजना (आपकी सहमति से)
4. आपकी पूछताछ और सहायता अनुरोधों का जवाब देना
5. हमारी सेवाओं और उपयोगकर्ता अनुभव में सुधार करना
6. कानूनी दायित्वों का पालन करना

## 4. डेटा साझाकरण और प्रकटीकरण

हम आपकी जानकारी साझा कर सकते हैं:
- **सेवा प्रदाताओं** के साथ: तीसरे पक्ष जो हमारी सेवा संचालित करने में हमारी सहायता करते हैं
- **व्यावसायिक भागीदारों** के साथ: संयुक्त मार्केटिंग या सेवा पेशकशों के लिए
- **कानूनी अनुपालन**: जब कानून द्वारा आवश्यक हो या हमारे अधिकारों की रक्षा के लिए

हम आपकी व्यक्तिगत जानकारी तीसरे पक्षों को नहीं बेचते हैं।

## 5. डेटा सुरक्षा

हम आपके डेटा की सुरक्षा के लिए उपयुक्त तकनीकी और संगठनात्मक उपाय लागू करते हैं, जिनमें शामिल हैं:
- ट्रांज़िट और स्टोरेज में डेटा एन्क्रिप्शन
- नियमित सुरक्षा मूल्यांकन
- पहुँच नियंत्रण और प्रमाणीकरण
- डेटा सुरक्षा पर कर्मचारी प्रशिक्षण

## 6. आपके अधिकार

आपके स्थान के आधार पर, आपके पास निम्नलिखित का अधिकार हो सकता है:
- अपने व्यक्तिगत डेटा तक पहुँच
- गलत डेटा को सुधारना
- अपना डेटा हटाना
- प्रोसेसिंग पर आपत्ति करना
- डेटा पोर्टेबिलिटी
- सहमति वापस लेना

## 7. कुकीज़ और ट्रैकिंग

हम कुकीज़ और समान तकनीकों का उपयोग निम्नलिखित के लिए करते हैं:
- आपकी प्राथमिकताएँ याद रखना
- उपयोग पैटर्न का विश्लेषण करना
- व्यक्तिगत सामग्री प्रदान करना
- हमारी सेवाओं में सुधार करना

आप अपने ब्राउज़र सेटिंग्स के माध्यम से कुकीज़ को नियंत्रित कर सकते हैं।

## 8. बच्चों की गोपनीयता

हमारी सेवा 13 वर्ष से कम आयु के बच्चों के लिए नहीं है। हम जानबूझकर 13 वर्ष से कम आयु के बच्चों से जानकारी एकत्र नहीं करते हैं।

## 9. इस नीति में परिवर्तन

हम समय-समय पर इस गोपनीयता नीति को अपडेट कर सकते हैं। हम इस पृष्ठ पर नई नीति पोस्ट करके और "अंतिम अपडेट" तिथि को अपडेट करके किसी भी बदलाव की सूचना देंगे।

## 10. हमसे संपर्क करें

यदि आपके इस गोपनीयता नीति के बारे में प्रश्न हैं, तो कृपया हमसे privacy@klarvido.com पर संपर्क करें।

---

*यह प्लेसहोल्डर सामग्री है और इसकी समीक्षा किसी कानूनी सलाहकार द्वारा नहीं की गई है। इस पर भरोसा करने से पहले इसे अपनी अंतिम गोपनीयता नीति से बदलें।*
`,
  [Locale.ARABIC]: `
## 1. مقدمة

توضح سياسة الخصوصية هذه كيف تقوم Klarvido بجمع معلوماتك واستخدامها والإفصاح عنها وحمايتها عند استخدامك لخدمتنا. يرجى قراءة سياسة الخصوصية هذه بعناية.

## 2. المعلومات التي نجمعها

### 2.1 البيانات الشخصية
قد نجمع معلومات تعريف شخصية، بما في ذلك على سبيل المثال لا الحصر:
- الاسم وعنوان البريد الإلكتروني
- رقم الهاتف
- معلومات الفوترة والدفع
- بيانات الاستخدام والتفضيلات

### 2.2 المعلومات التي يتم جمعها تلقائيًا
عند وصولك إلى خدمتنا، نقوم تلقائيًا بجمع:
- معلومات الجهاز والمتصفح
- عنوان IP وبيانات الموقع
- أنماط الاستخدام والتفضيلات
- ملفات تعريف الارتباط وتقنيات التتبع المشابهة

## 3. كيف نستخدم معلوماتك

نستخدم المعلومات التي نجمعها من أجل:
1. تقديم خدمتنا والحفاظ عليها
2. معالجة المعاملات وإرسال المعلومات ذات الصلة
3. إرسال اتصالات ترويجية (بموافقتك)
4. الرد على استفساراتك وطلبات الدعم
5. تحسين خدماتنا وتجربة المستخدم
6. الامتثال للالتزامات القانونية

## 4. مشاركة البيانات والإفصاح عنها

قد نشارك معلوماتك مع:
- **مقدمي الخدمات**: أطراف ثالثة تساعدنا في تشغيل خدمتنا
- **الشركاء التجاريين**: من أجل عروض تسويقية أو خدمية مشتركة
- **الامتثال القانوني**: عندما يقتضي القانون ذلك أو لحماية حقوقنا

نحن لا نبيع معلوماتك الشخصية لأطراف ثالثة.

## 5. أمن البيانات

نطبق تدابير تقنية وتنظيمية مناسبة لحماية بياناتك، بما في ذلك:
- تشفير البيانات أثناء النقل وفي حالة التخزين
- تقييمات أمنية منتظمة
- ضوابط الوصول والمصادقة
- تدريب الموظفين على حماية البيانات

## 6. حقوقك

اعتمادًا على موقعك، قد يكون لديك الحق في:
- الوصول إلى بياناتك الشخصية
- تصحيح البيانات غير الدقيقة
- حذف بياناتك
- الاعتراض على المعالجة
- نقل البيانات
- سحب الموافقة

## 7. ملفات تعريف الارتباط والتتبع

نستخدم ملفات تعريف الارتباط والتقنيات المشابهة من أجل:
- تذكر تفضيلاتك
- تحليل أنماط الاستخدام
- تقديم محتوى مخصص
- تحسين خدماتنا

يمكنك التحكم في ملفات تعريف الارتباط من خلال إعدادات متصفحك.

## 8. خصوصية الأطفال

خدمتنا غير موجهة للأطفال دون سن 13 عامًا. نحن لا نجمع عن قصد معلومات من الأطفال دون سن 13 عامًا.

## 9. التغييرات على هذه السياسة

قد نقوم بتحديث سياسة الخصوصية هذه من وقت لآخر. سنُعلمك بأي تغييرات من خلال نشر السياسة الجديدة على هذه الصفحة وتحديث تاريخ "آخر تحديث".

## 10. تواصل معنا

إذا كانت لديك أي أسئلة حول سياسة الخصوصية هذه، فيرجى التواصل معنا على privacy@klarvido.com.

---

*هذا محتوى مؤقت لم تتم مراجعته من قبل مستشار قانوني. استبدله بسياسة الخصوصية النهائية الخاصة بك قبل الاعتماد عليه.*
`,
  [Locale.CHINESE]: `
## 1. 简介

本隐私政策说明了 Klarvido 在您使用我们的服务时如何收集、使用、披露和保护您的信息。请仔细阅读本隐私政策。

## 2. 我们收集的信息

### 2.1 个人数据
我们可能会收集个人身份信息,包括但不限于:
- 姓名和电子邮件地址
- 电话号码
- 账单和付款信息
- 使用数据和偏好设置

### 2.2 自动收集的信息
当您访问我们的服务时,我们会自动收集:
- 设备和浏览器信息
- IP 地址和位置数据
- 使用模式和偏好设置
- Cookie 和类似的跟踪技术

## 3. 我们如何使用您的信息

我们使用收集到的信息用于:
1. 提供和维护我们的服务
2. 处理交易并发送相关信息
3. 发送促销通讯(在您同意的情况下)
4. 回应您的咨询和支持请求
5. 改进我们的服务和用户体验
6. 履行法律义务

## 4. 数据共享与披露

我们可能会与以下各方共享您的信息:
- **服务提供商**:协助我们运营服务的第三方
- **业务合作伙伴**:用于联合营销或服务推广
- **法律合规**:在法律要求或为保护我们的权利时

我们不会将您的个人信息出售给第三方。

## 5. 数据安全

我们采取适当的技术和组织措施来保护您的数据,包括:
- 传输和存储中的数据加密
- 定期安全评估
- 访问控制和身份验证
- 员工数据保护培训

## 6. 您的权利

根据您所在的地区,您可能有权:
- 访问您的个人数据
- 更正不准确的数据
- 删除您的数据
- 反对处理
- 数据可携带性
- 撤回同意

## 7. Cookie 与跟踪

我们使用 Cookie 和类似技术用于:
- 记住您的偏好
- 分析使用模式
- 提供个性化内容
- 改进我们的服务

您可以通过浏览器设置控制 Cookie。

## 8. 儿童隐私

我们的服务不面向 13 岁以下的儿童。我们不会故意收集 13 岁以下儿童的信息。

## 9. 本政策的变更

我们可能会不时更新本隐私政策。我们将通过在本页面发布新政策并更新"最后更新"日期来通知您任何变更。

## 10. 联系我们

如果您对本隐私政策有任何疑问,请通过 privacy@klarvido.com 与我们联系。

---

*这是占位内容,尚未经过法律顾问审查。在依赖它之前,请将其替换为您最终确定的隐私政策。*
`,
};
