from typing import List, Dict

# Scalable daily vocabulary data structure. 
# This maps the specific day_id (e.g., from the URL) to the required words for that day.
DAILY_VOCABULARY: Dict[str, List[Dict[str, str]]] = {
    "day_1_greetings": [
        {
            "id": "1",
            "english_intro": "Casual Greeting ('Hello'):",
            "usage_context": "Casual Greeting",
            "target_arabic": "مَرْحَبَا",
            "transliteration": "Mar7aba"
        },
        {
            "id": "2",
            "english_intro": "Casual Response ('Double Hello'):",
            "usage_context": "Casual Response",
            "target_arabic": "مَرْحَبَتيْن",
            "transliteration": "Mar7abtyn"
        },
        {
            "id": "3",
            "english_intro": "Formal Greeting ('Peace be upon you'):",
            "usage_context": "Formal Greeting",
            "target_arabic": "السَّلَامُ عَلَيْكُم",
            "transliteration": "Assalaamu 3alaykom"
        },
        {
            "id": "4",
            "english_intro": "Formal Response ('And upon you be peace'):",
            "usage_context": "Formal Response",
            "target_arabic": "وَعَلَيْكُمُ السَّلَام",
            "transliteration": "Wa 3alaykom assalaam"
        },
        {
            "id": "5",
            "english_intro": "Sympathetic Greeting (to a male):",
            "usage_context": "Greeting to a male",
            "target_arabic": "يَعْطِيكْ الْعَافِيَة",
            "transliteration": "Ya3Teek il 3aafyeh"
        },
        {
            "id": "6",
            "english_intro": "Sympathetic Greeting (to a female):",
            "usage_context": "Greeting to a female",
            "target_arabic": "يَعْطِيكِ الْعَافِيَة",
            "transliteration": "Ya3Teeki il 3aafyeh"
        },
        {
            "id": "7",
            "english_intro": "Response (to a male):",
            "usage_context": "Response to a male",
            "target_arabic": "الله يَعَافِيك",
            "transliteration": "Allah y3aafeek"
        },
        {
            "id": "8",
            "english_intro": "Response (to a female):",
            "usage_context": "Response to a female",
            "target_arabic": "الله يَعَافِيكِ",
            "transliteration": "Allah y3aafeeki"
        }
    ],
    "day_2_good_morning": [
        {
            "id": "1",
            "english_intro": "Let's review 'Good Morning':",
            "target_arabic": "صَبَاحِ الْخَيْر",
            "transliteration": "Sabah al-khair"
        },
        {
            "id": "2",
            "english_intro": "And here is the response, 'Morning of Light':",
            "target_arabic": "صَبَاحِ النُّور",
            "transliteration": "Sabah an-noor"
        },
        {
            "id": "3",
            "english_intro": "Say 'Good Afternoon' or 'Good Evening':",
            "target_arabic": "مَسَاءِ الْخَيْر",
            "transliteration": "Masaa2 il khair"
        },
        {
            "id": "4",
            "english_intro": "And the response, 'Evening of Light':",
            "target_arabic": "مَسَاءِ النُّور",
            "transliteration": "Masaa2 il noor"
        },
        {
            "id": "5",
            "english_intro": "Say 'Good Night' to a male:",
            "target_arabic": "تِصْبَح عَلَى خَيْر",
            "transliteration": "TiSba7 3ala khair"
        },
        {
            "id": "6",
            "english_intro": "Say 'Good Night' to a female:",
            "target_arabic": "تِصْبَحِي عَلَى خَيْر",
            "transliteration": "TiSba7i 3ala khair"
        },
        {
            "id": "7",
            "english_intro": "Say 'Good Night' to a group:",
            "target_arabic": "تِصْبَحُوا عَلَى خَيْر",
            "transliteration": "TiSba7u 3ala khair"
        },
        {
            "id": "8",
            "english_intro": "Respond to 'Good Night' (to a male):",
            "target_arabic": "وِنْتَ مِنْ أَهْلُه",
            "transliteration": "Ou inta min ahlo"
        },
        {
            "id": "9",
            "english_intro": "Respond to 'Good Night' (to a female):",
            "target_arabic": "وِنْتِ مِنْ أَهْلُه" ,
            "transliteration": "Ou inti min ahlo"
        },
        {
            "id": "10",
            "english_intro": "Respond to 'Good Night' (to a group):",
            "target_arabic": "وِنْتُو مِنْ أَهْلُه",
            "transliteration": "Ou intu min ahlo"
        },
        {
            "id": "11",
            "english_intro": "A second way to respond to 'Good Night' (to a male):",
            "target_arabic": "تِلاَقِي الْخَيْر",
            "transliteration": "Tlaa2-ee il khair"
        },
        {
            "id": "12",
            "english_intro": "The same response, to a female:",
            "target_arabic": "تِلاَقِي الْخَيْر",
            "transliteration": "Tlaa2-ee il khair"
        },
        {
            "id": "13",
            "english_intro": "And to a group:",
            "target_arabic": "تِلاَقُوا الْخَيْر",
            "transliteration": "Tlaa2u il khair"
        },
        {
            "id": "14",
            "english_intro": "A poetic way to say 'Good Morning' — 'morning of roses':",
            "target_arabic": "صَبَاحِ الْوَرْد",
            "transliteration": "Sabaa7 il ward"
        },
        {
            "id": "15",
            "english_intro": "Another poetic 'Good Morning' — 'morning of jasmine':",
            "target_arabic": "صَبَاحِ الْيَاسْمِين",
            "transliteration": "Sabaa7 il yasmeen"
        },
        {
            "id": "16",
            "english_intro": "A poetic 'Good Morning' — 'morning of ful flowers':",
            "target_arabic": "صَبَاحِ الْفُلّ",
            "transliteration": "Sabaa7 il foll"
        },
        {
            "id": "17",
            "english_intro": "A poetic 'Good Morning' — 'morning of honey':",
            "target_arabic": "صَبَاحِ الْعَسَل",
            "transliteration": "Sabaa7 il 3asal"
        }
    ],
    "day_3_pronouns": [
        {
            "id": "1",
            "english_intro": "Let's say 'I' in Arabic:",
            "target_arabic": "أَنَا",
            "evaluation_target": "أَنَا",
            "transliteration": "Anaa"
        },
        {
            "id": "2",
            "english_intro": "Now, 'You' for a male:",
            "target_arabic": "إِنْتَ",
            "evaluation_target": "إِنْتَ",
            "transliteration": "Inta"
        },
        {
            "id": "3",
            "english_intro": "And 'You' for a female:",
            "target_arabic": "إِنْتِ",
            "evaluation_target": "إِنْتِ",
            "transliteration": "Inti"
        },
        {
            "id": "4",
            "english_intro": "How about 'He':",
            "target_arabic": "هُوَّه",
            "evaluation_target": "هُوَّه",
            "transliteration": "Howweh"
        },
        {
            "id": "5",
            "english_intro": "And 'She':",
            "target_arabic": "هِيَّه",
            "evaluation_target": "هِيَّه",
            "transliteration": "Hiyyeh"
        },
        {
            "id": "6",
            "english_intro": "Moving to plurals, let's say 'We':",
            "target_arabic": "إِحْنَا",
            "evaluation_target": "إِحْنَا",
            "transliteration": "I7na"
        },
        {
            "id": "7",
            "english_intro": "And 'You' for a group:",
            "target_arabic": "إِنْتُو",
            "evaluation_target": "إِنْتُو",
            "transliteration": "Intu"
        },
        {
            "id": "8",
            "english_intro": "Finally, 'They':",
            "target_arabic": "هُمَّه",
            "evaluation_target": "هُمَّه",
            "transliteration": "Hommeh"
        }
    ],
    "day_4_names_introductions": [
        {
            "id": "1",
            "english_intro": "Ask a male 'What's your name?':",
            "target_arabic": "شُو اِسْمَك",
            "transliteration": "Shuu ismak"
        },
        {
            "id": "2",
            "english_intro": "Ask a female 'What's your name?':",
            "target_arabic": "شُو اِسْمِك",
            "transliteration": "Shuu ismik"
        },
        {
            "id": "3",
            "english_intro": "Say 'My name is...':",
            "target_arabic": "اِسْمِي",
            "transliteration": "Ismee"
        },
        {
            "id": "4",
            "english_intro": "Say 'Nice to meet you':",
            "target_arabic": "تَشَرَّفْنَا",
            "transliteration": "Tasharrafna"
        },
        {
            "id": "5",
            "english_intro": "Say 'Pleased to meet you':",
            "target_arabic": "فُرْصَة سَعِيدَة",
            "transliteration": "Fursa sa3eedah"
        }
    ],
    "day_5_how_are_you": [
        {
            "id": "1",
            "english_intro": "Ask a male 'How are you?':",
            "target_arabic": "كَيْفَ حَالُك",
            "transliteration": "Keef haalak"
        },
        {
            "id": "2",
            "english_intro": "Ask a female 'How are you?':",
            "target_arabic": "كَيْفَ حَالُكِ",
            "transliteration": "Keef haalik"
        },
        {
            "id": "3",
            "english_intro": "Ask 'What's your news?':",
            "target_arabic": "شُو أَخْبَارَك",
            "transliteration": "Shuu akhbaarak"
        },
        {
            "id": "4",
            "english_intro": "Casual 'How are you?' to male:",
            "target_arabic": "كَيَفَك",
            "transliteration": "Keefak"
        },
        {
            "id": "5",
            "english_intro": "Casual 'How are you?' to female:",
            "target_arabic": "كَيَفِك",
            "transliteration": "Keefik"
        },
        {
            "id": "6",
            "english_intro": "Say 'Praise be to Allah / I'm good':",
            "target_arabic": "الْحَمْدُ لِلَّه",
            "transliteration": "Alhamdulillah"
        },
        {
            "id": "7",
            "english_intro": "Say 'Great / Fine':",
            "target_arabic": "تَمَام",
            "transliteration": "Tamaam"
        }
    ],
    "day_6_where_are_you_from": [
        {
            "id": "1",
            "english_intro": "Ask a male 'Where are you from?':",
            "target_arabic": "مِنْ أَيْن أَنْت",
            "transliteration": "Min ayn anta"
        },
        {
            "id": "2",
            "english_intro": "Ask a female 'Where are you from?':",
            "target_arabic": "مِنْ أَيْن أَنْتِ",
            "transliteration": "Min ayn anti"
        },
        {
            "id": "3",
            "english_intro": "Say 'I am from...':",
            "target_arabic": "أَنَا مِنْ",
            "transliteration": "Ana min"
        },
        {
            "id": "4",
            "english_intro": "Say 'America':",
            "target_arabic": "أَمْرِيكَا",
            "transliteration": "Amreeka"
        },
        {
            "id": "5",
            "english_intro": "Say 'Canada':",
            "target_arabic": "كَنَدَا",
            "transliteration": "Kanada"
        },
        {
            "id": "6",
            "english_intro": "Say 'Australia':",
            "target_arabic": "أُوسْتُرَالِيَا",
            "transliteration": "Ostralya"
        },
        {
            "id": "7",
            "english_intro": "Say 'Britain':",
            "target_arabic": "بِرِيطَانِيَا",
            "transliteration": "Britanya"
        }
    ]
}

def get_vocabulary_for_day(day_id: str) -> List[Dict[str, str]]:
    """
    Retrieve the vocabulary list for a given day.
    Defaults to an empty list if the day_id is not found.
    """
    return DAILY_VOCABULARY.get(day_id, [])
