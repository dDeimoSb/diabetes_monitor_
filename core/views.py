from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from monitoring.models import Notifications

from .forms import DataExportForm, PasswordUpdateForm, PrediabetesRiskForm, UserProfileForm
from .services.export import (
    build_csv_export,
    build_export_rows,
    build_xlsx_export,
    get_export_entries,
    get_export_patient_search_results,
)
from .utils import (
    get_base_template,
    get_dashboard_url,
    get_notification_target_url,
    get_safe_redirect_target,
    get_user_role,
)

HOME_FEATURES = (
    {
        "title": "Справочные материалы",
        "description": "Короткие и понятные памятки о сахарном диабете, самоконтроле, сигналах риска и действиях в повседневной жизни.",
        "url_name": "materials",
        "link_text": "Открыть материалы",
    },
    {
        "title": "Тест риска предиабета",
        "description": "Небольшая анкета, которая помогает оценить есть ли у вас предиабет или сахарный диабет 2 типа.",
        "url_name": "prediabetes_test",
        "link_text": "Пройти тест",
    },
    {
        "title": "Вход и регистрация",
        "description": "Создайте учётную запись, чтобы начать вести дневник, или войдите в уже существующий аккаунт.",
        "url_name": "register",
        "link_text": "Перейти к регистрации",
    },
)

NOTIFICATIONS_PER_PAGE = 20

MATERIALS_SECTIONS = (
    {
        "slug": "about-diabetes",
        "title": "Что такое сахарный диабет?",
        "intro": (
            "Сахарный диабет - это заболевание обмена веществ, при котором в крови повышается уровень глюкозы.\n\n"
            "При сахарном диабете 1 типа вырабатывается очень мало инсулина или не вырабатывается вовсе, чаще "
            "всего из-за аутоимунного разрушения β-клеток поджелудочной железы.\n\n"
            "При сахарном диабете 2 типа вырабатывается инсулинорезистентность и постепенное снижение "
            "выработки инсулина.\n\n"
            "Инсулин - гормон, который вырабатывается в поджелудочной железе и помогает глюкозе поступать из крови в клетки. "
            "В норме глюкоза используется клетками как источник энергии.\n\n"
            "При диабете глюкоза не может полноценно попасть в клетки, поэтому её содержание в крови повышается, "
            "а клетки при этом испытывают энергетический дефицит."
        ),
        "items": ( ""
        ),
    },
    {
        "slug": "self-monitoring",
        "title": "Почему важен самоконтроль?",
        "intro": (
            "Основным источником глюкозы для организма являются продукты питания. После приёма пищи углеводы превращаются "
            "в глюкозу и поступают в кровь.\n\n"
            "Регулярный самоконтроль помогает вовремя замечать колебания уровня глюкозы, оценивать влияние питания, "
            "физической активности и терапии, а также предотвращать развитие осложнений.\n\n"
            "Постоянное наблюдение за показателями позволяет врачу и пациенту принимать более обоснованные решения "
            "по лечению и коррекции образа жизни."
        ),
        "items": ( ""
        ),
    },
    {
        "slug": "type-1-treatment",
        "title": "Основы лечения сахарного диабета 1 типа",
        "intro": (
            "На сегодняшний день основным методом лечения сахарного диабета 1 типа является инсулинотерапия.\n\n"
            "Подбор и коррекция доз инсулина проводятся с учётом уровня глюкозы крови, количества углеводов "
            "в пище и физической нагрузки.\n\n"
            "Инсулин может вводиться с помощью инсулиновых шприцев, шприц-ручек или инсулиновой помпы."
            ),
        "items": (
        ),
    },
    {
        "slug": "type-2-treatment",
        "title": "Основы лечения сахарного диабета 2 типа",
        "intro": (
            "Основным методом лечения сахарного диабета 2 типа является комплексный подход, "
            "который включает изменение образа жизни, диетотерапию, физическую активность и "
            "при необходимости медикаментозную терапию."
            ),
        "items": (
        ),
    },
    {
        "slug": "nutrition",
        "title": "Питание при избыточном весе",
        "intro": (
            "Рацион при диабете должен быть регулярным и понятным. Особенно важно учитывать количество "
            "углеводов в пище, поскольку именно они в наибольшей степени влияют на уровень глюкозы крови.\n\n"
            "При планировании рациона продукты условно разделяют на три группы:"
        ),
        "items": (
            {
                "title": "Продукты, которые можно употреблять без существенных ограничений:",
                "details": (
                    "Капуста (все виды), огурцы, салат листовой, зелень, помидоры, перец, кабачки, баклажаны, свекла, "
                    "морковь, стручковая фасоль, редис, редька, репа, зеленый горошек (молодой), шпинат, щавель, грибы;",
                    "Чай, кофе без сахара и сливок, минеральная вода, напитки на сахарозаменителях;",
                ),
                "notes": (
                    "Овощи можно употреблять в сыром, отварном, запечённом виде.",
                    "Использование жиров (масла, майонеза, сметаны) в приготовлении овощных блюд должно быть минимальным.",
                ),
            },
            {
                "title": "Продукты, которые следует употреблять в умеренном количестве:",
                "details": (
                    "Нежирное мясо (постная говядина, телятина), нежирная рыба (треска, судак, хек);",
                    "Молоко и кисломолочные продукты (нежирные), сыры менее 30% жирности, творог менее 5% жирности;",
                    "Картофель, кукуруза, зрелые зерна бобовых (горох, фасоль, чечевица), крупы, макаронные изделия, "
                    "хлеб и хлебобулочные изделия (не сдобные);",
                    "Фрукты;",
                    "Яйца.",
                ),
                "notes": (
                    "''Умеренное количество'' означает половину от Вашей привычной порции.",
                ),
            },
            {
                "title": "Продукты, которые необходимо исключить или максимально ограничить:",
                "details": (
                    "Масло сливочное, масло растительное*, сало, сметана, сливки, сыры более 30% жирности, "
                    "творог более 5% жирности, майонез;", 
                    "Жирное мясо, копчености, колбасные изделия, полуфабрикаты "
                    "(изделия из фарша, пельмени, замороженная пицца и т. п.), пироги, жирная рыба**, кожа птицы, "
                    "консервы мясные, рыбные и растительные в масле;",
                    "Орехи, семечки;",
                    "Cахар, мёд, варенье, джемы, сухофрукты, конфеты, шоколад, "
                    "печенье, изделия из сдобного теста, мороженое, пирожные, торты и др. кондитерские изделия;",
                    "Сладкие напитки (лимонады, фруктовые соки), алкогольные напитки.",
                ),
                "notes": (
                    "Следует по возможности исключить такой способ приготовления пищи как жарение.",
                    "Старайтесь использовать посуду, позволяющую готовить пищу без добавления жира.",
                    "*растительное масло является необходимой частью ежедневного рациона, "
                    "однако достаточно употреблять его в очень небольших количествах",
                    "**в жирных сортах рыбы содержатся полезные вещества, поэтому ограничение на неё менее строгое, "
                    "чем на жирное мясо.",
                )
            },
         ),
    },
    {
        "slug": "bread-units",
        "title": "Замена продуктов по системе хлебных единиц",
        "intro": (
            "Для практического расчёта углеводов может использоваться система хлебных единиц. Одна хлебная единица (1 ХЕ) "
            "соответствует количеству продукта, содержащему 10-12 г углеводов."
        ),
        "items": (
         ),
    },
    {
        "slug": "foot-care",
        "title": "Правила ухода за ногами при сахарном диабете",
        "intro": (
            "Даже небольшие повреждения кожи требуют внимания, поскольку при диабете они "
            "могут заживать хуже и приводить к осложнениям."
        ),
        "items": (
            "Ежедневно самостоятельно или с участием членов семьи осматривайте стопы, состояние кожи, включая промежутки между пальцами.",
            "Немедленно сообщите лечащему врачу о наличии потёртостей, порезов, трещин, царапин, ран и других повреждений кожи.",
            "Ежедневно мойте ноги тёплой водой температурой ниже 37°C и аккуратно просушивайте стопы, включая межпальцевые промежутки.",
            "При наличии ороговевшей кожи используйте пемзу или специальную пилку для кожи, но не лезвие и не ножницы.",
            "Не применяйте химические препараты или пластыри для удаления мозолей и ороговевшей кожи.",
            "При сухой коже стоп после мытья используйте крем с мочевиной, но не наносите его на межпальцевые промежутки.",
            "Осторожно обрабатывайте ногти, не закругляя уголки, и по возможности используйте пилочку вместо режущих инструментов.",
            "Для согревания ног пользуйтесь тёплыми носками, а не грелкой или горячей водой.",
            "Носите бесшовные носки или носки со швами наружу и меняйте их ежедневно.",
            "Не ходите босиком дома и на улице и не надевайте обувь на босую ногу.",
            "При необходимости проконсультируйтесь со специалистом кабинета «Диабетическая стопа» или ортопедом по поводу профилактической обуви.",
            "Ежедневно осматривайте обувь: нет ли внутри инородных предметов и не завернулась ли стелька.",
            "При повреждении кожи не используйте спиртосодержащие и красящие растворы; для обработки подходят бесцветные водные антисептики.",
        ),
    },
    {
        "slug": "protein-kidneys",
        "title": "Содержание белка в продуктах питания",
        "intro": (
            "Для того, чтобы поддержать почки в хорошем состоянии, при снижении их функции необходимо "
            "соблюдать ограничение в питании белковой пищи. Более полную информацию Вам даст Ваш лечащий врач."
        ),
        "items": (
            "Животные белки содержатся в мясе, рыбе, птице, молочных и морских продуктах, яйцах.",
            "Животные белки считаются наиболее ценными; ориентировочно их количество может составлять около 0,8 г на килограмм массы "
            "тела в сутки, однако окончательные рекомендации даются лечащим врачом."
        ),
    },
    {
        "slug": "additional-restrictions",
        "title": "Дополнительные пищевые ограничения",
        "intro": (
            "При необходимости может потребоваться ограничение продуктов, богатых калием, а также ограничение "
            "поваренной соли. Эти решения зависят от состояния здоровья и должны уточняться у врача."
        ),
        "items": (
            "К продуктам с высоким содержанием калия относятся, в частности, орехи, горох желтый, капуста брюссельская, "
            "краснокочанная, картофель, ревень, редька, шпинат, щавель, изюм, курага чернослив, персики, абрикосы, "
            "ананас, бананы, кизил, финики, шелковица, смородина черная.",
            "Общее количество соли в сутки не должно превышать 5 г, то есть одну неполную чайную ложку.",
            "Следует по возможности исключить или резко ограничить соленья (огурцы, помидоры, капуста), маринады, "
            "сельдь, любые консервы и готовые соусы.",
        ),
    }
)

MATERIALS_SOURCES = (
    {
        "title": "Клинические рекомендации Минздрава РФ Сахарный диабет 1 типа у взрослых",
        "url": "https://cr.minzdrav.gov.ru/view-cr/286_3",
    },
    {
        "title": "Клинические рекомендации Минздрава РФ Сахарный диабет 2 типа у взрослых",
        "url": "https://cr.minzdrav.gov.ru/view-cr/290_2",
    },
)


BREAD_UNITS_TABLE = {
    "title": "Таблица 1. Замена продуктов по системе хлебных единиц",
    "headers": (
        "Единицы измерения",
        "Продукты",
        "Количество на 1 ХЕ",
    ),
    "rows": (
        {"group": "Хлеб и хлебобулочные изделия<sup>1</sup>"},
        {"cells": ("1 кусок", "Белый хлеб", "20 г")},
        {"cells": ("1 кусок", "Черный хлеб", "25 г")},
        {"cells": ("", "Сухари", "15 г")},
        {"cells": ("", "Крекеры (сухое печенье)", "15 г")},
        {"cells": ("1 ст. ложка", "Панировочные сухари", "15 г")},
        {
            "note": (
                "<sup>1</sup> Пельмени, блины, оладьи, пирожки, сырники, вареники и котлеты также "
                "содержат углеводы, но количество ХЕ зависит от размера и рецепта изделия."
            )
        },
        {"group": "Макаронные изделия"},
        {
            "cells": (
                "1-2 ст. ложки в зависимости от формы изделия",
                "Вермишель, лапша, рожки, макароны<sup>2</sup>",
                "15 г",
            )
        },
        {
            "note": (
                "<sup>2</sup> В несваренном виде 1 ХЕ содержится в 15 г продукта; в вареном виде - "
                "в 2-4 ст. ложках (40-50 г) в зависимости от формы изделия."
            )
        },
        {"group": "Крупы, кукуруза, мука"},
        {"cells": ("1 ст. ложка", "Крупа (любая)<sup>3</sup>", "15 г")},
        {"cells": ("1/2 початка, среднего", "Кукуруза", "100 г")},
        {
            "cells": (
                "3 ст. ложки",
                "Кукуруза консервированная (без жидкости)",
                "60 г",
            )
        },
        {"cells": ("4 ст. ложки", "Кукурузные хлопья", "15 г")},
        {
            "cells": (
                "10 ст. ложек",
                "Попкорн («воздушная» кукуруза)",
                "15 г",
            )
        },
        {"cells": ("1 ст. ложка", "Мука", "15 г")},
        {"cells": ("2 ст. ложки", "Овсяные хлопья", "15 г")},
        {
            "note": (
                "<sup>3</sup> Сырая крупа; в вареном виде (каша) 1 ХЕ содержится в 2 ст. ложках "
                "с горкой (50 г)."
            )
        },
        {"group": "Картофель"},
        {
            "cells": (
                "1 штука, средняя",
                "Картофель сырой и вареный (без кожуры)",
                "65 г",
            )
        },
        {"cells": ("2 ст. ложки", "Картофельное пюре", "75 г")},
        {"cells": ("2 ст. ложки", "Жареный картофель", "35-45 г")},
        {"cells": ("", "Сухой картофель (чипсы)", "25 г")},
        {"group": "Молоко и жидкие молочные продукты"},
        {"cells": ("1 стакан", "Молоко", "200 мл")},
        {"cells": ("1 стакан", "Ряженка", "250 мл")},
        {"cells": ("1 стакан", "Кефир", "250 мл")},
        {"cells": ("1 стакан", "Сливки", "200 мл")},
        {"cells": ("", "Йогурт натуральный", "150-200 г")},
        {"group": "Фрукты и ягоды (с косточками и кожурой)"},
        {"cells": ("2-3 штуки", "Абрикосы", "110 г")},
        {"cells": ("1 штука, крупная", "Айва", "140 г")},
        {"cells": ("1 кусок (поперечный срез)", "Ананас", "140 г")},
        {"cells": ("1 кусок", "Арбуз", "270 г")},
        {"cells": ("1 штука, средний", "Апельсин", "150 г")},
        {"cells": ("1/2 штуки, среднего", "Банан", "70 г")},
        {"cells": ("7 ст. ложек", "Брусника", "140 г")},
        {"cells": ("12 штук, небольших", "Виноград", "70 г")},
        {"cells": ("15 штук", "Вишня", "90 г")},
        {"cells": ("1 штука, средний", "Гранат", "170 г")},
        {"cells": ("1/2 штуки, крупного", "Грейпфрут", "170 г")},
        {"cells": ("1 штука, маленькая", "Груша", "90 г")},
        {"cells": ("1 кусок", "Дыня", "100 г")},
        {"cells": ("8 ст. ложек", "Ежевика", "140 г")},
        {"cells": ("1 штука", "Инжир", "80 г")},
        {"cells": ("1 штука, крупный", "Киви", "110 г")},
        {"cells": ("10 штук, средних", "Клубника", "160 г")},
        {"cells": ("6 ст. ложек", "Крыжовник", "120 г")},
        {"cells": ("8 ст. ложек", "Малина", "160 г")},
        {"cells": ("1/2 штуки, небольшого", "Манго", "110 г")},
        {"cells": ("2 штуки, средних", "Мандарины", "150 г")},
        {"cells": ("1 штука, средний", "Персик", "120 г")},
        {"cells": ("3 штуки, небольших", "Сливы", "90 г")},
        {"cells": ("7 ст. ложек", "Смородина", "120 г")},
        {"cells": ("1 штука, средний", "Финик (сушеный)", "15 г")},
        {"cells": ("1/2 штуки, средней", "Хурма", "70 г")},
        {"cells": ("12 штук", "Черешня", "90 г")},
        {"cells": ("7 ст. ложек", "Черника", "90 г")},
        {"cells": ("1 штука, маленькое", "Яблоко", "90 г")},
        {"cells": ("1/2 стакана", "Фруктовый сок", "100 мл")},
        {"cells": ("", "Сухофрукты", "20 г")},
        {"group": "Овощи, бобовые, орехи, семечки"},
        {"cells": ("3 штуки, средних", "Морковь", "200 г")},
        {"cells": ("1 штука, средняя", "Свекла", "150 г")},
        {"cells": ("7 ст. ложек", "Арахис", "100 г")},
        {"cells": ("1 ст. ложка, сухих", "Бобы", "20 г")},
        {"cells": ("7 ст. ложек, свежего", "Горошек зеленый", "100 г")},
        {"cells": ("3 ст. ложки, вареной", "Фасоль", "50 г")},
        {"cells": ("", "Орехи (неочищенные)<sup>4</sup>", "60-90 г")},
        {"cells": ("", "Семечки подсолнечника (неочищенные)", "200 г")},
        {"note": "<sup>4</sup> Для орехов количество зависит от вида."},
        {"group": "Другие продукты"},
        {"cells": ("2 ч. ложки", "Сахар-песок", "10 г")},
        {"cells": ("2 куска", "Сахар кусковой", "10 г")},
        {"cells": ("1/2 стакана", "Газированная вода на сахаре", "100 мл")},
        {"cells": ("1 стакан", "Квас", "250 мл")},
        {"cells": ("", "Мороженое", "65 г")},
        {"cells": ("", "Шоколад", "20 г")},
        {"cells": ("", "Мед", "12 г")},
    ),
}

ANIMAL_PROTEIN_TABLE = {
    "title": "Таблица 2. Содержание белка в продуктах животного происхождения",
    "headers": (
        "Продукт (вес в граммах или объем)",
        "Белок, г",
    ),
    "rows": (
        {"cells": ("Мясо (100 г или 1 жареный антрекот)", "30")},
        {"cells": ("Птица (100 г или 1/4 курицы весом в сыром виде 1 кг)", "30")},
        {"cells": ("Рыба (100 г)", "25")},
        {"group": "Субпродукты (100 г)"},
        {"cells": ("Почки", "35")},
        {"cells": ("Сердце, язык", "12")},
        {"group": "Молочные продукты"},
        {"cells": ("Творог 100 г", "16")},
        {"cells": ("Сырок творожный (100 г или 1 шт.)", "7")},
        {"cells": ("Молоко, кисломолочные продукты - напитки (1 стакан)", "7")},
        {"cells": ("Брынза вымоченная (25 г)", "6")},
        {"cells": ("Мороженое (100 г или 1 пачка)", "3")},
        {"cells": ("Сметана (100 г или 1/2 стакана)", "3")},
        {"cells": ("Яйца (1 шт.)", "5")},
    ),
}

STARCH_PROTEIN_TABLE = {
    "title": "Таблица 3. Содержание белка в крахмалистых продуктах",
    "headers": (
        "Продукт (вес в граммах или объем)",
        "Белок, г",
    ),
    "rows": (
        {"cells": ("Хлеб 25 г или 1 кусок", "2")},
        {"group": "Каши (1 стакан)"},
        {"cells": ("Овсяная, манная, гречневая", "4")},
        {"cells": ("Рисовая, пшенная", "6")},
        {"cells": ("Макаронные изделия (1 стакан)", "6")},
        {"cells": ("Картофель (100 г или 1 средняя картофелина)", "2")},
        {"cells": ("Фасоль (100 г)", "21")},
        {"cells": ("Чечевица (100 г)", "24")},
    ),
}

MATERIALS_TABLES = {
    "bread-units": (BREAD_UNITS_TABLE,),
    "protein-kidneys": (ANIMAL_PROTEIN_TABLE, STARCH_PROTEIN_TABLE),
}


def _get_patient_or_public_base_template(user):
    return "base_patient_app.html" if get_user_role(user) == "patient" else "base_public.html"


def _get_patient_or_public_dashboard_url(user):
    return get_dashboard_url(user) if get_user_role(user) == "patient" else "/"


def _require_cabinet_role(request):
    role = get_user_role(request.user)
    if role in {"doctor", "patient"}:
        return role

    messages.warning(request, "Раздел доступен только врачу или пациенту.")
    return ""


def _get_pagination_query(request, page_param="page"):
    query_params = request.GET.copy()
    query_params.pop(page_param, None)
    return query_params.urlencode()


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "feature_cards": HOME_FEATURES,
        },
    )


def materials(request):
    materials_sections = tuple(
        {
            **section,
            "tables": MATERIALS_TABLES.get(section["slug"], ()),
        }
        for section in MATERIALS_SECTIONS
    )

    return render(
        request,
        "core/materials.html",
        {
            "base_template": _get_patient_or_public_base_template(request.user),
            "dashboard_url": _get_patient_or_public_dashboard_url(request.user),
            "materials_sections": materials_sections,
            "materials_sources": MATERIALS_SOURCES,
        },
    )


def prediabetes_test(request):
    result = None
    form = PrediabetesRiskForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        result = form.get_result()

    return render(
        request,
        "core/prediabetes_test.html",
        {
            "base_template": _get_patient_or_public_base_template(request.user),
            "dashboard_url": _get_patient_or_public_dashboard_url(request.user),
            "form": form,
            "result": result,
        },
    )


@login_required
def profile(request):
    role = _require_cabinet_role(request)
    if not role:
        return redirect("home")
    base_template = get_base_template(request.user)

    profile_form = UserProfileForm(
        request.POST or None,
        instance=request.user,
        user=request.user,
        prefix="profile",
    )
    password_form = PasswordUpdateForm(
        request.POST or None,
        user=request.user,
        prefix="password",
    )

    action = request.POST.get("action")
    if request.method == "POST":
        if action == "profile":
            password_form = PasswordUpdateForm(user=request.user, prefix="password")
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Данные профиля сохранены.")
                return redirect("profile")
        elif action == "password":
            profile_form = UserProfileForm(
                instance=request.user,
                user=request.user,
                prefix="profile",
            )
            if password_form.is_valid() and password_form.has_change_requested():
                password_form.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, "Пароль обновлён.")
                return redirect("profile")
            if password_form.is_valid() and not password_form.has_change_requested():
                messages.info(request, "Введите новый пароль, чтобы изменить его.")
        else:
            messages.error(request, "Не удалось определить действие формы.")

    context = {
        "base_template": base_template,
        "profile_form": profile_form,
        "password_form": password_form,
        "role": role,
        "dashboard_url": get_dashboard_url(request.user),
        "role_label": "врача" if role == "doctor" else "пациента",
    }
    return render(request, "core/profile.html", context)


@login_required
def notifications(request):
    if not _require_cabinet_role(request):
        return redirect("home")
    base_template = get_base_template(request.user)
    queryset = (
        Notifications.objects.filter(recipient_user=request.user)
        .select_related("critical_event__entry__patient__user")
        .order_by("is_read", "-created_at", "-notification_id")
    )

    notifications_page = Paginator(
        queryset,
        NOTIFICATIONS_PER_PAGE,
    ).get_page(request.GET.get("page"))

    notification_items = [
        {
            "notification": notification,
            "target_url": get_notification_target_url(request.user, notification),
        }
        for notification in notifications_page.object_list
    ]

    context = {
        "base_template": base_template,
        "notification_items": notification_items,
        "notifications_page": notifications_page,
        "pagination_query": _get_pagination_query(request),
        "unread_count": queryset.filter(is_read=False).count(),
        "total_count": queryset.count(),
        "dashboard_url": get_dashboard_url(request.user),
    }
    return render(request, "core/notifications.html", context)


@login_required
def mark_notification_read(request, notification_id):
    if not _require_cabinet_role(request):
        return redirect("home")
    if request.method != "POST":
        return redirect("notifications")

    notification = get_object_or_404(
        Notifications,
        notification_id=notification_id,
        recipient_user=request.user,
    )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
        messages.success(request, "Уведомление отмечено как прочитанное.")

    return redirect(
        get_safe_redirect_target(
            request,
            request.POST.get("next"),
            reverse("notifications"),
        )
    )


@login_required
def export_data(request):
    if not _require_cabinet_role(request):
        return redirect("home")
    is_doctor = get_user_role(request.user) == "doctor"
    initial = {
        "start_date": timezone.localdate() - timedelta(days=30),
        "end_date": timezone.localdate(),
        "export_format": "csv",
    }
    patient_query = (
        request.POST.get("patient_query")
        or request.GET.get("patient_query")
        or ""
    ).strip()
    patient_search_results = (
        get_export_patient_search_results(request.user, patient_query)
        if is_doctor
        else None
    )
    form = DataExportForm(
        request.POST or None,
        user=request.user,
        initial=initial if request.method == "GET" else None,
    )

    if request.method == "POST" and form.is_valid():
        entries = get_export_entries(request.user, form.cleaned_data)
        rows = build_export_rows(entries)
        filename = (
            f"monitoring_{form.cleaned_data['start_date']:%Y%m%d}_"
            f"{form.cleaned_data['end_date']:%Y%m%d}"
        )

        if form.cleaned_data["export_format"] == "excel":
            return build_xlsx_export(rows, filename)
        return build_csv_export(rows, filename)

    context = {
        "base_template": get_base_template(request.user),
        "form": form,
        "dashboard_url": get_dashboard_url(request.user),
        "is_doctor": is_doctor,
        "patient_query": patient_query,
        "patient_search_results": patient_search_results,
    }
    return render(request, "core/export.html", context)
