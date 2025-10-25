    def _update_xliff_targets(self, xliff_content: Dict[str, Any], translated_strings: Dict[str, str]) -> Dict[str, Any]:
        """
        Update XLIFF target elements with translated strings.
        
        Args:
            xliff_content: Original XLIFF content
            translated_strings: Dictionary of translated strings
            
        Returns:
            Updated XLIFF content with target elements
        """
        updated_content = xliff_content.copy()
        
        if 'files' in updated_content:
            for file_data in updated_content['files']:
                if 'trans-units' in file_data:
                    for unit in file_data['trans-units']:
                        if 'id' in unit and unit['id'] in translated_strings:
                            unit['target'] = translated_strings[unit['id']]
        
        return updated_content
    
    def _translate_csv_content(self, csv_content: Dict[str, Any], source_lang: str, target_lang: str, 
                              ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate CSV content for a specific target language.
        
        Args:
            csv_content: CSV content dictionary
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation
            
        Returns:
            Updated CSV content with translated strings
        """
        if 'translations' not in csv_content:
            return csv_content
        
        # Extract source language strings
        source_strings = {}
        for key, lang_translations in csv_content['translations'].items():
            if isinstance(lang_translations, dict) and source_lang in lang_translations:
                source_strings[key] = lang_translations[source_lang]
        
        # Translate the strings
        translated_strings = self._translate_flat_dict(source_strings, source_lang, target_lang, ui_safe, glossary_id)
        
        # Update the CSV content
        updated_content = csv_content.copy()
        for key, translated_value in translated_strings.items():
            if key in updated_content['translations']:
                if target_lang not in updated_content['translations'][key]:
                    updated_content['translations'][key] = updated_content['translations'][key].copy()
                updated_content['translations'][key][target_lang] = translated_value
        
        return updated_content
    
    def _translate_xlsx_content(self, xlsx_content: Dict[str, Any], source_lang: str, target_lang: str, 
                               ui_safe: bool = False, glossary_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Translate XLSX content for a specific target language.
        
        Args:
            xlsx_content: XLSX content dictionary
            source_lang: Source language code
            target_lang: Target language code
            ui_safe: If True, ensure translations will not be longer than original text
            glossary_id: Glossary ID to use for translation
            
        Returns:
            Updated XLSX content with translated strings
        """
        if 'translations' not in xlsx_content:
            return xlsx_content
        
        # Extract source language strings
        source_strings = {}
        for key, lang_translations in xlsx_content['translations'].items():
            if isinstance(lang_translations, dict) and source_lang in lang_translations:
                source_strings[key] = lang_translations[source_lang]
        
        # Translate the strings
        translated_strings = self._translate_flat_dict(source_strings, source_lang, target_lang, ui_safe, glossary_id)
        
        # Update the XLSX content
        updated_content = xlsx_content.copy()
        for key, translated_value in translated_strings.items():
            if key in updated_content['translations']:
                if target_lang not in updated_content['translations'][key]:
                    updated_content['translations'][key] = updated_content['translations'][key].copy()
                updated_content['translations'][key][target_lang] = translated_value
        
        return updated_content
