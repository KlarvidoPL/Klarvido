import { Locale } from '@sb/webapp-core/config/i18n';

// Keyed by locale rather than run through intl.formatMessage(): ICU MessageFormat
// parsing collapses blank lines, which silently destroys markdown's block structure
// (headings/paragraphs/lists all merge into one block) - fine for short UI strings,
// not for multi-paragraph content like this. See staticContentPage.component.tsx.
export const termsAndConditionsContent: Partial<Record<Locale, string>> = {
  [Locale.ENGLISH]: `
## 1. Introduction

Welcome to Klarvido. These Terms and Conditions govern your use of our platform and services. By accessing or using our service, you agree to be bound by these terms.

## 2. Definitions

- **"Service"** refers to the application, website, and any related services provided by Klarvido.
- **"User"** refers to any individual who accesses or uses the Service.
- **"Content"** refers to any text, images, or other materials uploaded to the Service.

## 3. User Accounts

### 3.1 Registration
To access certain features of the Service, you must register for an account. You agree to:
- Provide accurate and complete information
- Maintain the security of your account credentials
- Promptly update any changes to your information

### 3.2 Account Responsibilities
You are responsible for all activities that occur under your account. Please notify us immediately if you suspect any unauthorized use.

## 4. Acceptable Use

You agree not to:
1. Use the Service for any illegal purposes
2. Violate any applicable laws or regulations
3. Infringe on the rights of others
4. Upload malicious code or content
5. Attempt to gain unauthorized access to the Service

## 5. Intellectual Property

All content, trademarks, and other intellectual property on the Service are owned by Klarvido or its licensors. You may not use, copy, or distribute any content without permission.

## 6. Limitation of Liability

To the maximum extent permitted by law, Klarvido shall not be liable for any indirect, incidental, special, or consequential damages arising from your use of the Service.

## 7. Changes to Terms

We reserve the right to modify these Terms at any time. We will notify users of any material changes via email or through the Service.

## 8. Contact

If you have any questions about these Terms, please contact us at legal@klarvido.com.

---

*This is placeholder content and has not been reviewed by legal counsel. Replace it with your finalized Terms and Conditions before relying on it.*
`,
  [Locale.POLISH]: `
## 1. Wprowadzenie

Witamy w Klarvido. Niniejszy Regulamin określa zasady korzystania z naszej platformy i usług. Uzyskując dostęp do naszej usługi lub korzystając z niej, zgadzasz się na przestrzeganie niniejszych warunków.

## 2. Definicje

- **„Usługa"** oznacza aplikację, stronę internetową oraz wszelkie powiązane usługi świadczone przez Klarvido.
- **„Użytkownik"** oznacza dowolną osobę, która uzyskuje dostęp do Usługi lub z niej korzysta.
- **„Treść"** oznacza dowolny tekst, obrazy lub inne materiały przesłane do Usługi.

## 3. Konta użytkowników

### 3.1 Rejestracja
Aby uzyskać dostęp do niektórych funkcji Usługi, musisz zarejestrować konto. Zobowiązujesz się do:
- Podawania dokładnych i kompletnych informacji
- Zachowania bezpieczeństwa danych logowania do konta
- Niezwłocznego aktualizowania wszelkich zmian w swoich danych

### 3.2 Odpowiedzialność za konto
Ponosisz odpowiedzialność za wszystkie działania podejmowane w ramach Twojego konta. Prosimy o natychmiastowe powiadomienie nas w przypadku podejrzenia nieautoryzowanego użycia.

## 4. Dozwolone użytkowanie

Zobowiązujesz się nie:
1. Korzystać z Usługi w celach niezgodnych z prawem
2. Naruszać obowiązujących przepisów prawa
3. Naruszać praw innych osób
4. Przesyłać złośliwego kodu ani treści
5. Podejmować prób uzyskania nieautoryzowanego dostępu do Usługi

## 5. Własność intelektualna

Wszystkie treści, znaki towarowe i inna własność intelektualna dostępna w Usłudze są własnością Klarvido lub jego licencjodawców. Nie wolno wykorzystywać, kopiować ani rozpowszechniać żadnych treści bez zezwolenia.

## 6. Ograniczenie odpowiedzialności

W maksymalnym zakresie dozwolonym przez prawo Klarvido nie ponosi odpowiedzialności za jakiekolwiek szkody pośrednie, przypadkowe, szczególne lub wynikowe powstałe w związku z korzystaniem z Usługi.

## 7. Zmiany w Regulaminie

Zastrzegamy sobie prawo do zmiany niniejszego Regulaminu w dowolnym momencie. O wszelkich istotnych zmianach powiadomimy użytkowników za pośrednictwem poczty e-mail lub Usługi.

## 8. Kontakt

Jeśli masz pytania dotyczące niniejszego Regulaminu, skontaktuj się z nami pod adresem legal@klarvido.com.

---

*Jest to treść zastępcza, która nie została zweryfikowana przez prawnika. Przed poleganiem na niej zastąp ją finalną wersją Regulaminu.*
`,
  [Locale.GERMAN]: `
## 1. Einleitung

Willkommen bei Klarvido. Diese Allgemeinen Geschäftsbedingungen regeln Ihre Nutzung unserer Plattform und Dienste. Durch den Zugriff auf oder die Nutzung unseres Dienstes stimmen Sie zu, an diese Bedingungen gebunden zu sein.

## 2. Begriffsbestimmungen

- **„Dienst"** bezeichnet die Anwendung, die Website und alle damit verbundenen von Klarvido bereitgestellten Dienste.
- **„Nutzer"** bezeichnet jede Person, die auf den Dienst zugreift oder ihn nutzt.
- **„Inhalt"** bezeichnet Text, Bilder oder andere Materialien, die in den Dienst hochgeladen werden.

## 3. Benutzerkonten

### 3.1 Registrierung
Um bestimmte Funktionen des Dienstes nutzen zu können, müssen Sie ein Konto registrieren. Sie verpflichten sich:
- Genaue und vollständige Informationen anzugeben
- Die Sicherheit Ihrer Kontodaten zu gewährleisten
- Änderungen Ihrer Informationen umgehend zu aktualisieren

### 3.2 Kontoverantwortung
Sie sind für alle Aktivitäten verantwortlich, die unter Ihrem Konto stattfinden. Bitte benachrichtigen Sie uns umgehend, wenn Sie eine unbefugte Nutzung vermuten.

## 4. Zulässige Nutzung

Sie verpflichten sich, Folgendes zu unterlassen:
1. Den Dienst für illegale Zwecke zu nutzen
2. Gegen geltende Gesetze oder Vorschriften zu verstoßen
3. Die Rechte Dritter zu verletzen
4. Schadhaften Code oder Inhalte hochzuladen
5. Zu versuchen, unbefugten Zugriff auf den Dienst zu erlangen

## 5. Geistiges Eigentum

Alle Inhalte, Marken und sonstiges geistiges Eigentum im Dienst sind Eigentum von Klarvido oder seinen Lizenzgebern. Sie dürfen keine Inhalte ohne Genehmigung nutzen, kopieren oder verbreiten.

## 6. Haftungsbeschränkung

Soweit gesetzlich zulässig, haftet Klarvido nicht für indirekte, zufällige, besondere oder Folgeschäden, die sich aus Ihrer Nutzung des Dienstes ergeben.

## 7. Änderungen der Bedingungen

Wir behalten uns das Recht vor, diese Bedingungen jederzeit zu ändern. Wir werden Nutzer über wesentliche Änderungen per E-Mail oder über den Dienst informieren.

## 8. Kontakt

Wenn Sie Fragen zu diesen Bedingungen haben, kontaktieren Sie uns bitte unter legal@klarvido.com.

---

*Dies ist ein Platzhaltertext, der nicht von einem Rechtsberater geprüft wurde. Ersetzen Sie ihn durch Ihre endgültigen Allgemeinen Geschäftsbedingungen, bevor Sie sich darauf verlassen.*
`,
  [Locale.SPANISH]: `
## 1. Introducción

Bienvenido a Klarvido. Estos Términos y Condiciones rigen el uso de nuestra plataforma y servicios. Al acceder o utilizar nuestro servicio, aceptas quedar vinculado por estos términos.

## 2. Definiciones

- **"Servicio"** se refiere a la aplicación, el sitio web y cualquier servicio relacionado proporcionado por Klarvido.
- **"Usuario"** se refiere a cualquier persona que acceda o utilice el Servicio.
- **"Contenido"** se refiere a cualquier texto, imagen u otro material subido al Servicio.

## 3. Cuentas de usuario

### 3.1 Registro
Para acceder a determinadas funciones del Servicio, debes registrar una cuenta. Aceptas:
- Proporcionar información precisa y completa
- Mantener la seguridad de las credenciales de tu cuenta
- Actualizar sin demora cualquier cambio en tu información

### 3.2 Responsabilidades de la cuenta
Eres responsable de todas las actividades que ocurran bajo tu cuenta. Notifícanos de inmediato si sospechas de algún uso no autorizado.

## 4. Uso aceptable

Aceptas no:
1. Utilizar el Servicio con fines ilegales
2. Infringir cualquier ley o normativa aplicable
3. Vulnerar los derechos de terceros
4. Subir código o contenido malicioso
5. Intentar obtener acceso no autorizado al Servicio

## 5. Propiedad intelectual

Todo el contenido, las marcas comerciales y demás propiedad intelectual del Servicio son propiedad de Klarvido o de sus licenciantes. No puedes usar, copiar ni distribuir ningún contenido sin permiso.

## 6. Limitación de responsabilidad

En la medida máxima permitida por la ley, Klarvido no será responsable de ningún daño indirecto, incidental, especial o consecuente derivado del uso del Servicio.

## 7. Cambios en los Términos

Nos reservamos el derecho de modificar estos Términos en cualquier momento. Notificaremos a los usuarios sobre cualquier cambio significativo por correo electrónico o a través del Servicio.

## 8. Contacto

Si tienes alguna pregunta sobre estos Términos, contáctanos en legal@klarvido.com.

---

*Este es contenido de marcador de posición que no ha sido revisado por un asesor legal. Reemplázalo con tus Términos y Condiciones definitivos antes de basarte en él.*
`,
  [Locale.FRENCH]: `
## 1. Introduction

Bienvenue chez Klarvido. Les présentes Conditions Générales régissent votre utilisation de notre plateforme et de nos services. En accédant à notre service ou en l'utilisant, vous acceptez d'être lié par ces conditions.

## 2. Définitions

- **« Service »** désigne l'application, le site web et tout service connexe fourni par Klarvido.
- **« Utilisateur »** désigne toute personne qui accède au Service ou l'utilise.
- **« Contenu »** désigne tout texte, image ou autre matériel téléversé sur le Service.

## 3. Comptes utilisateur

### 3.1 Inscription
Pour accéder à certaines fonctionnalités du Service, vous devez créer un compte. Vous acceptez de :
- Fournir des informations exactes et complètes
- Assurer la sécurité des identifiants de votre compte
- Mettre à jour rapidement toute modification de vos informations

### 3.2 Responsabilités liées au compte
Vous êtes responsable de toutes les activités effectuées sous votre compte. Veuillez nous avertir immédiatement si vous soupçonnez une utilisation non autorisée.

## 4. Utilisation acceptable

Vous acceptez de ne pas :
1. Utiliser le Service à des fins illégales
2. Enfreindre les lois ou réglementations applicables
3. Porter atteinte aux droits d'autrui
4. Téléverser du code ou du contenu malveillant
5. Tenter d'accéder au Service sans autorisation

## 5. Propriété intellectuelle

L'ensemble du contenu, des marques et autres éléments de propriété intellectuelle du Service appartiennent à Klarvido ou à ses concédants de licence. Vous ne pouvez pas utiliser, copier ou distribuer de contenu sans autorisation.

## 6. Limitation de responsabilité

Dans toute la mesure permise par la loi, Klarvido ne pourra être tenu responsable de tout dommage indirect, accessoire, spécial ou consécutif résultant de votre utilisation du Service.

## 7. Modifications des Conditions

Nous nous réservons le droit de modifier ces Conditions à tout moment. Nous informerons les utilisateurs de tout changement important par e-mail ou via le Service.

## 8. Contact

Pour toute question concernant ces Conditions, veuillez nous contacter à legal@klarvido.com.

---

*Il s'agit d'un contenu provisoire qui n'a pas été examiné par un conseiller juridique. Remplacez-le par vos Conditions Générales définitives avant de vous y fier.*
`,
  [Locale.HINDI]: `
## 1. परिचय

Klarvido में आपका स्वागत है। ये नियम एवं शर्तें हमारे प्लेटफ़ॉर्म और सेवाओं के आपके उपयोग को नियंत्रित करती हैं। हमारी सेवा तक पहुँचकर या उसका उपयोग करके, आप इन शर्तों से बाध्य होने के लिए सहमत होते हैं।

## 2. परिभाषाएँ

- **"सेवा"** का अर्थ Klarvido द्वारा प्रदान किया गया एप्लिकेशन, वेबसाइट और कोई भी संबंधित सेवाएँ हैं।
- **"उपयोगकर्ता"** का अर्थ ऐसा कोई भी व्यक्ति है जो सेवा तक पहुँचता है या उसका उपयोग करता है।
- **"सामग्री"** का अर्थ सेवा पर अपलोड की गई कोई भी टेक्स्ट, चित्र या अन्य सामग्री है।

## 3. उपयोगकर्ता खाते

### 3.1 पंजीकरण
सेवा की कुछ सुविधाओं तक पहुँचने के लिए, आपको खाता पंजीकृत करना होगा। आप सहमत हैं कि आप:
- सटीक और पूर्ण जानकारी प्रदान करेंगे
- अपने खाते की साख की सुरक्षा बनाए रखेंगे
- अपनी जानकारी में किसी भी बदलाव को तुरंत अपडेट करेंगे

### 3.2 खाता उत्तरदायित्व
आप अपने खाते के अंतर्गत होने वाली सभी गतिविधियों के लिए जिम्मेदार हैं। यदि आपको किसी अनधिकृत उपयोग का संदेह हो तो कृपया हमें तुरंत सूचित करें।

## 4. स्वीकार्य उपयोग

आप सहमत हैं कि आप नहीं करेंगे:
1. किसी भी अवैध उद्देश्य के लिए सेवा का उपयोग
2. किसी भी लागू कानून या विनियम का उल्लंघन
3. दूसरों के अधिकारों का उल्लंघन
4. दुर्भावनापूर्ण कोड या सामग्री अपलोड करना
5. सेवा तक अनधिकृत पहुँच प्राप्त करने का प्रयास

## 5. बौद्धिक संपदा

सेवा पर सभी सामग्री, ट्रेडमार्क और अन्य बौद्धिक संपदा Klarvido या उसके लाइसेंसदाताओं की संपत्ति है। आप अनुमति के बिना किसी भी सामग्री का उपयोग, प्रतिलिपि या वितरण नहीं कर सकते।

## 6. दायित्व की सीमा

कानून द्वारा अनुमत अधिकतम सीमा तक, Klarvido आपकी सेवा के उपयोग से उत्पन्न किसी भी अप्रत्यक्ष, आकस्मिक, विशेष या परिणामी क्षति के लिए उत्तरदायी नहीं होगा।

## 7. शर्तों में परिवर्तन

हम किसी भी समय इन शर्तों को संशोधित करने का अधिकार सुरक्षित रखते हैं। हम किसी भी महत्वपूर्ण परिवर्तन के बारे में उपयोगकर्ताओं को ईमेल या सेवा के माध्यम से सूचित करेंगे।

## 8. संपर्क करें

यदि आपके इन शर्तों के बारे में कोई प्रश्न हैं, तो कृपया हमसे legal@klarvido.com पर संपर्क करें।

---

*यह प्लेसहोल्डर सामग्री है और इसकी समीक्षा किसी कानूनी सलाहकार द्वारा नहीं की गई है। इस पर भरोसा करने से पहले इसे अपने अंतिम नियम एवं शर्तों से बदलें।*
`,
  [Locale.ARABIC]: `
## 1. مقدمة

مرحبًا بك في Klarvido. تحكم هذه الشروط والأحكام استخدامك لمنصتنا وخدماتنا. من خلال الوصول إلى خدمتنا أو استخدامها، فإنك توافق على الالتزام بهذه الشروط.

## 2. التعريفات

- تشير **"الخدمة"** إلى التطبيق والموقع الإلكتروني وأي خدمات ذات صلة تقدمها Klarvido.
- يشير **"المستخدم"** إلى أي فرد يصل إلى الخدمة أو يستخدمها.
- يشير **"المحتوى"** إلى أي نص أو صور أو مواد أخرى يتم تحميلها إلى الخدمة.

## 3. حسابات المستخدمين

### 3.1 التسجيل
للوصول إلى ميزات معينة من الخدمة، يجب عليك تسجيل حساب. أنت توافق على:
- تقديم معلومات دقيقة وكاملة
- الحفاظ على أمان بيانات اعتماد حسابك
- تحديث أي تغييرات في معلوماتك على الفور

### 3.2 مسؤوليات الحساب
أنت مسؤول عن جميع الأنشطة التي تحدث ضمن حسابك. يرجى إخطارنا فورًا إذا اشتبهت في أي استخدام غير مصرح به.

## 4. الاستخدام المقبول

أنت توافق على عدم:
1. استخدام الخدمة لأي أغراض غير قانونية
2. انتهاك أي قوانين أو لوائح معمول بها
3. انتهاك حقوق الآخرين
4. تحميل تعليمات برمجية أو محتوى ضار
5. محاولة الوصول غير المصرح به إلى الخدمة

## 5. الملكية الفكرية

جميع المحتويات والعلامات التجارية والملكية الفكرية الأخرى على الخدمة مملوكة لشركة Klarvido أو الجهات المرخِّصة لها. لا يجوز لك استخدام أي محتوى أو نسخه أو توزيعه دون إذن.

## 6. تحديد المسؤولية

إلى الحد الأقصى الذي يسمح به القانون، لن تكون Klarvido مسؤولة عن أي أضرار غير مباشرة أو عرضية أو خاصة أو تبعية ناشئة عن استخدامك للخدمة.

## 7. التغييرات على الشروط

نحتفظ بالحق في تعديل هذه الشروط في أي وقت. سنقوم بإخطار المستخدمين بأي تغييرات جوهرية عبر البريد الإلكتروني أو من خلال الخدمة.

## 8. التواصل معنا

إذا كانت لديك أي أسئلة حول هذه الشروط، فيرجى التواصل معنا على legal@klarvido.com.

---

*هذا محتوى مؤقت لم تتم مراجعته من قبل مستشار قانوني. استبدله بشروطك وأحكامك النهائية قبل الاعتماد عليه.*
`,
  [Locale.CHINESE]: `
## 1. 简介

欢迎使用 Klarvido。本服务条款规范您对我们平台和服务的使用。访问或使用我们的服务即表示您同意受本条款约束。

## 2. 定义

- **"服务"** 指 Klarvido 提供的应用程序、网站及任何相关服务。
- **"用户"** 指访问或使用本服务的任何个人。
- **"内容"** 指上传至本服务的任何文本、图像或其他材料。

## 3. 用户账户

### 3.1 注册
要访问本服务的某些功能,您必须注册账户。您同意:
- 提供准确、完整的信息
- 维护账户凭据的安全
- 及时更新您信息的任何变更

### 3.2 账户责任
您对账户下发生的所有活动负责。如果您怀疑存在任何未经授权的使用,请立即通知我们。

## 4. 可接受使用

您同意不会:
1. 将本服务用于任何非法目的
2. 违反任何适用法律或法规
3. 侵犯他人权利
4. 上传恶意代码或内容
5. 试图未经授权访问本服务

## 5. 知识产权

本服务上的所有内容、商标及其他知识产权均归 Klarvido 或其许可方所有。未经许可,您不得使用、复制或分发任何内容。

## 6. 责任限制

在法律允许的最大范围内,Klarvido 对因您使用本服务而产生的任何间接、附带、特殊或后果性损害不承担责任。

## 7. 条款变更

我们保留随时修改本条款的权利。我们将通过电子邮件或本服务通知用户任何重大变更。

## 8. 联系我们

如果您对本条款有任何疑问,请通过 legal@klarvido.com 与我们联系。

---

*这是占位内容,尚未经过法律顾问审查。在依赖它之前,请将其替换为您最终确定的服务条款。*
`,
};
