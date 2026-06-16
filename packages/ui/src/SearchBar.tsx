import React from 'react';
import { Searchbar as PaperSearchbar } from 'react-native-paper';
import { StyleSheet, ViewStyle } from 'react-native';

export interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  onClear?: () => void;
  style?: ViewStyle;
}

export const SearchBar: React.FC<SearchBarProps> = ({
  value,
  onChangeText,
  placeholder = 'Search voice notes...',
  onClear,
  style,
}) => {
  return (
    <PaperSearchbar
      placeholder={placeholder}
      onChangeText={onChangeText}
      value={value}
      onClearIconPress={onClear}
      style={[styles.searchBar, style]}
      inputStyle={styles.input}
      accessibilityLabel="Search box"
      accessibilityRole="search"
    />
  );
};

const styles = StyleSheet.create({
  searchBar: {
    borderRadius: 12,
    elevation: 0,
    borderWidth: 1,
    borderColor: 'transparent',
    minHeight: 48,
  },
  input: {
    minHeight: 48,
    alignSelf: 'center',
  },
});
