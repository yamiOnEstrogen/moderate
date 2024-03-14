@echo off

REM Loop through the alphabet from A to Z
for %%i in (A B C D E F G H I J K L M N O P Q R S T U V W X Y Z) do (
    REM Create a folder with the current letter in ./websites
    mkdir ".\websites\%%i"
    REM Create a .gitkeep file inside the folder
    copy NUL ".\websites\%%i\.gitkeep" >NUL
)

echo Folders A-Z created in ./websites with .gitkeep files.
