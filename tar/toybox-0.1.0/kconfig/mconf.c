/*
 * Copyright (C) 2002 Roman Zippel <zippel@linux-m68k.org>
 * Released under the terms of the GNU GPL v2.0.
 *
 * Introduced single menu mode (show all sub-menus in one large tree).
 * 2002-11-06 Petr Baudis <pasky@ucw.cz>
 *
 * i18n, 2005, Arnaldo Carvalho de Melo <acme@conectiva.com.br>
 */

#include <sys/ioctl.h>
#include <sys/wait.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include <locale.h>

#define LKC_DIRECT_LINK
#include "lkc.h"
#include "lxdialog/dialog.h"

static char menu_backtitle[128];
static const char mconf_readme[] = N_(
"Overview\n"
"--------\n"
"Some features may be built directly into the project.\n"
"Some may be made into loadable runtime modules.  Some features\n"
"may be completely removed altogether.  There are also certain\n"
"parameters which are not really features, but must be\n"
"entered in as decimal or hexadecimal numbers or possibly text.\n"
"\n"
"Menu items beginning with [*], <M> or [ ] represent features\n"
"configured to be built in, modularized or removed respectively.\n"
"Pointed brackets <> represent module capable features.\n"
"\n"
"To change any of these features, highlight it with the cursor\n"
"keys and press <Y> to build it in, <M> to make it a module or\n"
"<N> to removed it.  You may also press the <Space Bar> to cycle\n"
"through the available options (ie. Y->N->M->Y).\n"
"\n"
"Some additional keyboard hints:\n"
"\n"
"Menus\n"
"----------\n"
"o  Use the Up/Down arrow keys (cursor keys) to highlight the item\n"
"   you wish to change or submenu wish to select and press <Enter>.\n"
"   Submenus are designated by \"--->\".\n"
"\n"
"   Shortcut: Press the option's highlighted letter (hotkey).\n"
"             Pressing a hotkey more than once will sequence\n"
"             through all visible items which use that hotkey.\n"
"\n"
"   You may also use the <PAGE UP> and <PAGE DOWN> keys to scroll\n"
"   unseen options into view.\n"
"\n"
"o  To exit a menu use the cursor keys to highlight the <Exit> button\n"
"   and press <ENTER>.\n"
"\n"
"   Shortcut: Press <ESC><ESC> or <E> or <X> if there is no hotkey\n"
"             using those letters.  You may press a single <ESC>, but\n"
"             there is a delayed response which you may find annoying.\n"
"\n"
"   Also, the <TAB> and cursor keys will cycle between <Select>,\n"
"   <Exit> and <Help>\n"
"\n"
"o  To get help with an item, use the cursor keys to highlight <Help>\n"
"   and Press <ENTER>.\n"
"\n"
"   Shortcut: Press <H> or <?>.\n"
"\n"
"\n"
"Radiolists  (Choice lists)\n"
"-----------\n"
"o  Use the cursor keys to select the option you wish to set and press\n"
"   <S> or the <SPACE BAR>.\n"
"\n"
"   Shortcut: Press the first letter of the option you wish to set then\n"
"             press <S> or <SPACE BAR>.\n"
"\n"
"o  To see available help for the item, use the cursor keys to highlight\n"
"   <Help> and Press <ENTER>.\n"
"\n"
"   Shortcut: Press <H> or <?>.\n"
"\n"
"   Also, the <TAB> and cursor keys will cycle between <Select> and\n"
"   <Help>\n"
"\n"
"\n"
"Data Entry\n"
"-----------\n"
"o  Enter the requested information and press <ENTER>\n"
"   If you are entering hexadecimal values, it is not necessary to\n"
"   add the '0x' prefix to the entry.\n"
"\n"
"o  For help, use the <TAB> or cursor keys to highlight the help option\n"
"   and press <ENTER>.  You can try <TAB><H> as well.\n"
"\n"
"\n"
"Text Box    (Help Window)\n"
"--------\n"
"o  Use the cursor keys to scroll up/down/left/right.  The VI editor\n"
"   keys h,j,k,l function here as do <SPACE BAR> and <B> for those\n"
"   who are familiar with less and lynx.\n"
"\n"
"o  Press <E>, <X>, <Enter> or <Esc><Esc> to exit.\n"
"\n"
"\n"
"Alternate Configuration Files\n"
"-----------------------------\n"
"Menuconfig supports the use of alternate configuration files for\n"
"those who, for various reasons, find it necessary to switch\n"
"between different configurations.\n"
"\n"
"At the end of the main menu you will find two options.  One is\n"
"for saving the current configuration to a file of your choosing.\n"
"The other option is for loading a previously saved alternate\n"
"configuration.\n"
"\n"
"Even if you don't use alternate configuration files, but you\n"
"find during a Menuconfig session that you have completely messed\n"
"up your settings, you may use the \"Load Alternate...\" option to\n"
"restore your previously saved settings from \".config\" without\n"
"restarting Menuconfig.\n"
"\n"
"Other information\n"
"-----------------\n"
"If you use Menuconfig in an XTERM window make sure you have your\n"
"$TERM variable set to point to a xterm definition which supports color.\n"
"Otherwise, Menuconfig will look rather bad.  Menuconfig will not\n"
"display correctly in a RXVT window because rxvt displays only one\n"
"intensity of color, bright.\n"
"\n"
"Menuconfig will display larger menus on screens or xterms which are\n"
"set to display more than the standard 25 row by 80 column geometry.\n"
"In order for this to work, the \"stty size\" command must be able to\n"
"display the screen's current row and column geometry.  I STRONGLY\n"
"RECOMMEND that you make sure you do NOT have the shell variables\n"
"LINES and COLUMNS exported into your environment.  Some distributions\n"
"export those variables via /etc/profile.  Some ncurses programs can\n"
"become confused when those variables (LINES & COLUMNS) don't reflect\n"
"the true screen size.\n"
"\n"
"Optional personality available\n"
"------------------------------\n"
"If you prefer to have all of the options listed in a single\n"
"menu, rather than the default multimenu hierarchy, run the menuconfig\n"
"with MENUCONFIG_MODE environment variable set to single_menu. Example:\n"
"\n"
"make MENUCONFIG_MODE=single_menu menuconfig\n"
"\n"
"<Enter> will then unroll the appropriate category, or enfold it if it\n"
"is already unrolled.\n"
"\n"
"Note that this mode can eventually be a little more CPU expensive\n"
"(especially with a larger number of unrolled categories) than the\n"
"default mode.\n"
"\n"
"Different color themes available\n"
"--------------------------------\n"
"It is possible to select different color themes using the variable\n"
"MENUCONFIG_COLOR. To select a theme use:\n"
"\n"
"make MENUCONFIG_COLOR=<theme> menuconfig\n"
"\n"
"Available themes are\n"
" mono       => selects colors suitable for monochrome displays\n"
" blackbg    => selects a color scheme with black background\n"
" classic    => theme with blue background. The classic look\n"
" bluetitle  => a LCD friendly version of classic. (default)\n"
"\n"),
menu_instructions[] = N_(
	"Arrow keys navigate the menu.  "
	"<Enter> selects submenus --->.  "
	"Highlighted letters are hotkeys.  "
	"Pressing <Y> includes, <N> excludes, <M> modularizes features.  "
	"Press <Esc><Esc> to exit, <?> for Help, </> for Search.  "
	"Legend: [*] built-in  [ ] excluded  <M> module  < > module capable"),
radiolist_instructions[] = N_(
	"Use the arrow keys to navigate this window or "
	"press the hotkey of the item you wish to select "
	"followed by the <SPACE BAR>. "
	"Press <?> for additional information about this option."),
inputbox_instructions_int[] = N_(
	"Please enter a decimal value. "
	"Fractions will not be accepted.  "
	"Use the <TAB> key to move from the input field to the buttons below it."),
inputbox_instructions_hex[] = N_(
	"Please enter a hexadecimal value. "
	"Use the <TAB> key to move from the input field to the buttons below it."),
inputbox_instructions_string[] = N_(
	"Please enter a string value. "
	"Use the <TAB> key to move from the input field to the buttons below it."),
setmod_text[] = N_(
	"This feature depends on another which has been configured as a module.\n"
	"As a result, this feature will be built as a module."),
nohelp_text[] = N_(
	"There is no help available for this option.\n"),
load_config_text[] = N_(
	"Enter the name of the configuration file you wish to load.  "
	"Accept the name shown to restore the configuration you "
	"last retrieved.  Leave blank to abort."),
load_config_help[] = N_(
	"\n"
	"For various reasons, one may wish to keep several different\n"
	"configurations available on a single machine.\n"
	"\n"
	"If you have saved a previous configuration in a file other than the\n"
	"default, entering the name of the file here will allow you\n"
	"to modify that configuration.\n"
	"\n"
	"If you are uncertain, then you have probably never used alternate\n"
	"configuration files.  You should therefor leave this blank to abort.\n"),
save_config_text[] = N_(
	"Enter a filename to which this configuration should be saved "
	"as an alternate.  Leave blank to abort."),
save_config_help[] = N_(
	"\n"
	"For various reasons, one may wish to keep different\n"
	"configurations available on a single machine.\n"
	"\n"
	"Entering a file name here will allow you to later retrieve, modify\n"
	"and use the current configuration as an alternate to whatever\n"
	"configuration options you have selected at that time.\n"
	"\n"
	"If you are uncertain what all this means then you should probably\n"
	"leave this blank.\n"),
search_help[] = N_(
	"\n"
	"Search for CONFIG_ symbols and display their relations.\n"
	"Regular expressions are allowed.\n"
	"Example: search for \"^FOO\"\n"
	"Result:\n"
	"-----------------------------------------------------------------\n"
	"Symbol: FOO [=m]\n"
	"Prompt: Foo bus is used to drive the bar HW\n"
	"Defined at drivers/pci/Kconfig:47\n"
	"Depends on: X86_LOCAL_APIC && X86_IO_APIC || IA64\n"
	"Location:\n"
	"  -> Bus options (PCI, PCMCIA, EISA, MCA, ISA)\n"
	"    -> PCI support (PCI [=y])\n"
	"      -> PCI access mode (<choice> [=y])\n"
	"Selects: LIBCRC32\n"
	"Selected by: BAR\n"
	"-----------------------------------------------------------------\n"
	"o The line 'Prompt:' shows the text used in the menu structure for\n"
	"  this CONFIG_ symbol\n"
	"o The 'Defined at' line tell at what file / line number the symbol\n"
	"  is defined\n"
	"o The 'Depends on:' line tell what symbols needs to be defined for\n"
	"  this symbol to be visible in the menu (selectable)\n"
	"o The 'Location:' lines tell where in the menu structure this symbol\n"
	"  is located\n"
	"    A location followed by a [=y] indicate that this is a selectable\n"
	"    menu item - and current value is displayed inside brackets.\n"
	"o The 'Selects:' line tell what symbol will be automatically\n"
	"  selected if this symbol is selected (y or m)\n"
	"o The 'Selected by' line tell what symbol has selected this symbol\n"
	"\n"
	"Only relevant lines are shown.\n"
	"\n\n"
	"Search examples:\n"
	"Examples: USB	=> find all CONFIG_ symbols containing USB\n"
	"          ^USB => find all CONFIG_ symbols starting with USB\n"
	"          USB$ => find all CONFIG_ symbols ending with USB\n"
	"\n");

static char filename[PATH_MAX+1] = ".config";
static int indent;
static struct termios ios_org;
static int rows = 0, cols = 0;
static struct menu *current_menu;
static int child_count;
static int single_menu_mode;

static void conf(struct menu *menu);
static void conf_choice(struct menu *menu);
static void conf_string(struct menu *menu);
static void conf_load(void);
static void conf_save(void);
static void show_textbox(const char *title, const char *text, int r, int c);
static void show_helptext(const char *title, const char *text);
static void show_help(struct menu *menu);

static void init_wsize(void)
{
	struct winsize ws;
	char *env;

	if (!ioctl(STDIN_FILENO, TIOCGWINSZ, &ws)) {
		rows = ws.ws_row;
		cols = ws.ws_col;
	}

	if (!rows) {
		env = getenv("LINES");
		if (env)
			rows = atoi(env);
		if (!rows)
			rows = 24;
	}
	if (!cols) {
		env = getenv("COLUMNS");
		if (env)
			cols = atoi(env);
		if (!cols)
			cols = 80;
	}

	if (rows < 19 || cols < 80) {
		fprintf(stderr, N_("Your display is too small to run Menuconfig!\n"));
		fprintf(stderr, N_("It must be at least 19 lines by 80 columns.\n"));
		exit(1);
	}

	rows -= 4;
	cols -= 5;
}

static void get_prompt_str(struct gstr *r, struct property *prop)
{
	int i, j;
	struct menu *submenu[8], *menu;

	str_printf(r, "Prompt: %s\n", prop->text);
	str_printf(r, "  Defined at %s:%d\n", prop->menu->file->name,
		prop->menu->lineno);
	if (!expr_is_yes(prop->visible.expr)) {
		str_append(r, "  Depends on: ");
		expr_gstr_print(prop->visible.expr, r);
		str_append(r, "\n");
	}
	menu = prop->menu->parent;
	for (i = 0; menu != &rootmenu && i < 8; menu = menu->parent)
		submenu[i++] = menu;
	if (i > 0) {
		str_printf(r, "  Location:\n");
		for (j = 4; --i >= 0; j += 2) {
			menu = submenu[i];
			str_printf(r, "%*c-> %s", j, ' ', menu_get_prompt(menu));
			if (menu->sym) {
				str_printf(r, " (%s [=%s])", menu->sym->name ?
					menu->sym->name : "<choice>",
					sym_get_string_value(menu->sym));
			}
			str_append(r, "\n");
		}
	}
}

static void get_symbol_str(struct gstr *r, struct symbol *sym)
{
	bool hit;
	struct property *prop;

	str_printf(r, "Symbol: %s [=%s]\n", sym->name,
	                               sym_get_string_value(sym));
	for_all_prompts(sym, prop)
		get_prompt_str(r, prop);
	hit = false;
	for_all_properties(sym, prop, P_SELECT) {
		if (!hit) {
			str_append(r, "  Selects: ");
			hit = true;
		} else
			str_printf(r, " && ");
		expr_gstr_print(prop->expr, r);
	}
	if (hit)
		str_append(r, "\n");
	if (sym->rev_dep.expr) {
		str_append(r, "  Selected by: ");
		expr_gstr_print(sym->rev_dep.expr, r);
		str_append(r, "\n");
	}
	str_append(r, "\n\n");
}

static struct gstr get_relations_str(struct symbol **sym_arr)
{
	struct symbol *sym;
	struct gstr res = str_new();
	int i;

	for (i = 0; sym_arr && (sym = sym_arr[i]); i++)
		get_symbol_str(&res, sym);
	if (!i)
		str_append(&res, "No matches found.\n");
	return res;
}

static void search_conf(void)
{
	struct symbol **sym_arr;
	struct gstr res;
	int dres;
again:
	dialog_clear();
	dres = dialog_inputbox(_("Search Configuration Parameter"),
			      _("Enter CONFIG_ (sub)string to search for (omit CONFIG_)"),
			      10, 75, "");
	switch (dres) {
	case 0:
		break;
	case 1:
		show_helptext(_("Search Configuration"), search_help);
		goto again;
	default:
		return;
	}

	sym_arr = sym_re_search(dialog_input_result);
	res = get_relations_str(sym_arr);
	free(sym_arr);
	show_textbox(_("Search Results"), str_get(&res), 0, 0);
	str_free(&res);
}

static void build_conf(struct menu *menu)
{
	struct symbol *sym;
	struct property *prop;
	struct menu *child;
	int type, tmp, doint = 2;
	tristate val;
	char ch;

	if (!menu_is_visible(menu))
		return;

	sym = menu->sym;
	prop = menu->prompt;
	if (!sym) {
		if (prop && menu != current_menu) {
			const char *prompt = menu_get_prompt(menu);
			switch (prop->type) {
			case P_MENU:
				child_count++;
				if (single_menu_mode) {
					item_make("%s%*c%s",
						  menu->data ? "-->" : "++>",
						  indent + 1, ' ', prompt);
				} else
					item_make("   %*c%s  --->", indent + 1, ' ', prompt);

				item_set_tag('m');
				item_set_data(menu);
				if (single_menu_mode && menu->data)
					goto conf_childs;
				return;
			default:
				if (prompt) {
					child_count++;
					item_make("---%*c%s", indent + 1, ' ', prompt);
					item_set_tag(':');
					item_set_data(menu);
				}
			}
		} else
			doint = 0;
		goto conf_childs;
	}

	type = sym_get_type(sym);
	if (sym_is_choice(sym)) {
		struct symbol *def_sym = sym_get_choice_value(sym);
		struct menu *def_menu = NULL;

		child_count++;
		for (child = menu->list; child; child = child->next) {
			if (menu_is_visible(child) && child->sym == def_sym)
				def_menu = child;
		}

		val = sym_get_tristate_value(sym);
		if (sym_is_changable(sym)) {
			switch (type) {
			case S_BOOLEAN:
				item_make("[%c]", val == no ? ' ' : '*');
				break;
			case S_TRISTATE:
				switch (val) {
				case yes: ch = '*'; break;
				case mod: ch = 'M'; break;
				default:  ch = ' '; break;
				}
				item_make("<%c>", ch);
				break;
			}
			item_set_tag('t');
			item_set_data(menu);
		} else {
			item_make("   ");
			item_set_tag(def_menu ? 't' : ':');
			item_set_data(menu);
		}

		item_add_str("%*c%s", indent + 1, ' ', menu_get_prompt(menu));
		if (val == yes) {
			if (def_menu) {
				item_add_str(" (%s)", menu_get_prompt(def_menu));
				item_add_str("  --->");
				if (def_menu->list) {
					indent += 2;
					build_conf(def_menu);
					indent -= 2;
				}
			}
			return;
		}
	} else {
		if (menu == current_menu) {
			item_make("---%*c%s", indent + 1, ' ', menu_get_prompt(menu));
			item_set_tag(':');
			item_set_data(menu);
			goto conf_childs;
		}
		child_count++;
		val = sym_get_tristate_value(sym);
		if (sym_is_choice_value(sym) && val == yes) {
			item_make("   ");
			item_set_tag(':');
			item_set_data(menu);
		} else {
			switch (type) {
			case S_BOOLEAN:
				if (sym_is_changable(sym))
					item_make("[%c]", val == no ? ' ' : '*');
				else
					item_make("---");
				item_set_tag('t');
				item_set_data(menu);
				break;
			case S_TRISTATE:
				switch (val) {
				case yes: ch = '*'; break;
				case mod: ch = 'M'; break;
				default:  ch = ' '; break;
				}
				if (sym_is_changable(sym))
					item_make("<%c>", ch);
				else
					item_make("---");
				item_set_tag('t');
				item_set_data(menu);
				break;
			default:
				tmp = 2 + strlen(sym_get_string_value(sym)); /* () = 2 */
				item_make("(%s)", sym_get_string_value(sym));
				tmp = indent - tmp + 4;
				if (tmp < 0)
					tmp = 0;
				item_add_str("%*c%s%s", tmp, ' ', menu_get_prompt(menu),
					     (sym_has_value(sym) || !sym_is_changable(sym)) ?
					     "" : " (NEW)");
				item_set_tag('s');
				item_set_data(menu);
				goto conf_childs;
			}
		}
		item_add_str("%*c%s%s", indent + 1, ' ', menu_get_prompt(menu),
			  (sym_has_value(sym) || !sym_is_changable(sym)) ?
			  "" : " (NEW)");
		if (menu->prompt->type == P_MENU) {
			item_add_str("  --->");
			return;
		}
	}

conf_childs:
	indent += doint;
	for (child = menu->list; child; child = child->next)
		build_conf(child);
	indent -= doint;
}

static void conf(struct menu *menu)
{
	struct menu *submenu;
	const char *prompt = menu_get_prompt(menu);
	struct symbol *sym;
	struct menu *active_menu = NULL;
	int res;
	int s_scroll = 0;

	while (1) {
		item_reset();
		current_menu = menu;
		build_conf(menu);
		if (!child_count)
			break;
		if (menu == &rootmenu) {
			item_make("--- ");
			item_set_tag(':');
			item_make(_("    Load an Alternate Configuration File"));
			item_set_tag('L');
			item_make(_("    Save an Alternate Configuration File"));
			item_set_tag('S');
		}
		dialog_clear();
		res = dialog_menu(prompt ? prompt : _("Main Menu"),
				  _(menu_instructions),
				  active_menu, &s_scroll);
		if (res == 1 || res == KEY_ESC || res == -ERRDISPLAYTOOSMALL)
			break;
		if (!item_activate_selected())
			continue;
		if (!item_tag())
			continue;

		submenu = item_data();
		active_menu = item_data();
		if (submenu)
			sym = submenu->sym;
		else
			sym = NULL;

		switch (res) {
		case 0:
			switch (item_tag()) {
			case 'm':
				if (single_menu_mode)
					submenu->data = (void *) (long) !submenu->data;
				else
					conf(submenu);
				break;
			case 't':
				if (sym_is_choice(sym) && sym_get_tristate_value(sym) == yes)
					conf_choice(submenu);
				else if (submenu->prompt->type == P_MENU)
					conf(submenu);
				break;
			case 's':
				conf_string(submenu);
				break;
			case 'L':
				conf_load();
				break;
			case 'S':
				conf_save();
				break;
			}
			break;
		case 2:
			if (sym)
				show_help(submenu);
			else
				show_helptext("README", _(mconf_readme));
			break;
		case 3:
			if (item_is_tag('t')) {
				if (sym_set_tristate_value(sym, yes))
					break;
				if (sym_set_tristate_value(sym, mod))
					show_textbox(NULL, setmod_text, 6, 74);
			}
			break;
		case 4:
			if (item_is_tag('t'))
				sym_set_tristate_value(sym, no);
			break;
		case 5:
			if (item_is_tag('t'))
				sym_set_tristate_value(sym, mod);
			break;
		case 6:
			if (item_is_tag('t'))
				sym_toggle_tristate_value(sym);
			else if (item_is_tag('m'))
				conf(submenu);
			break;
		case 7:
			search_conf();
			break;
		}
	}
}

static void show_textbox(const char *title, const char *text, int r, int c)
{
	dialog_clear();
	dialog_textbox(title, text, r, c);
}

static void show_helptext(const char *title, const char *text)
{
	show_textbox(title, text, 0, 0);
}

static void show_help(struct menu *menu)
{
	struct gstr help = str_new();
	struct symbol *sym = menu->sym;

	if (sym->help)
	{
		if (sym->name) {
			str_printf(&help, "CONFIG_%s:\n\n", sym->name);
			str_append(&help, _(sym->help));
			str_append(&help, "\n");
		}
	} else {
		str_append(&help, nohelp_text);
	}
	get_symbol_str(&help, sym);
	show_helptext(menu_get_prompt(menu), str_get(&help));
	str_free(&help);
}

static void conf_choice(struct menu *menu)
{
	const char *prompt = menu_get_prompt(menu);
	struct menu *child;
	struct symbol *active;

	active = sym_get_choice_value(menu->sym);
	while (1) {
		int res;
		int selected;
		item_reset();

		current_menu = menu;
		for (child = menu->list; child; child = child->next) {
			if (!menu_is_visible(child))
				continue;
			item_make("%s", menu_get_prompt(child));
			item_set_data(child);
			if (child->sym == active)
				item_set_selected(1);
			if (child->sym == sym_get_choice_value(menu->sym))
				item_set_tag('X');
		}
		dialog_clear();
		res = dialog_checklist(prompt ? prompt : _("Main Menu"),
					_(radiolist_instructions),
					 15, 70, 6);
		selected = item_activate_selected();
		switch (res) {
		case 0:
			if (selected) {
				child = item_data();
				sym_set_tristate_value(child->sym, yes);
			}
			return;
		case 1:
			if (selected) {
				child = item_data();
				show_help(child);
				active = child->sym;
			} else
				show_help(menu);
			break;
		case KEY_ESC:
			return;
		case -ERRDISPLAYTOOSMALL:
			return;
		}
	}
}

static void conf_string(struct menu *menu)
{
	const char *prompt = menu_get_prompt(menu);

	while (1) {
		int res;
		char *heading;

		switch (sym_get_type(menu->sym)) {
		case S_INT:
			heading = _(inputbox_instructions_int);
			break;
		case S_HEX:
			heading = _(inputbox_instructions_hex);
			break;
		case S_STRING:
			heading = _(inputbox_instructions_string);
			break;
		default:
			heading = "Internal mconf error!";
		}
		dialog_clear();
		res = dialog_inputbox(prompt ? prompt : _("Main Menu"),
				      heading, 10, 75,
				      sym_get_string_value(menu->sym));
		switch (res) {
		case 0:
			if (sym_set_string_value(menu->sym, dialog_input_result))
				return;
			show_textbox(NULL, _("You have made an invalid entry."), 5, 43);
			break;
		case 1:
			show_help(menu);
			break;
		case KEY_ESC:
			return;
		}
	}
}

static void conf_load(void)
{

	while (1) {
		int res;
		dialog_clear();
		res = dialog_inputbox(NULL, load_config_text,
				      11, 55, filename);
		switch(res) {
		case 0:
			if (!dialog_input_result[0])
				return;
			if (!conf_read(dialog_input_result))
				return;
			show_textbox(NULL, _("File does not exist!"), 5, 38);
			break;
		case 1:
			show_helptext(_("Load Alternate Configuration"), load_config_help);
			break;
		case KEY_ESC:
			return;
		}
	}
}

static void conf_save(void)
{
	while (1) {
		int res;
		dialog_clear();
		res = dialog_inputbox(NULL, save_config_text,
				      11, 55, filename);
		switch(res) {
		case 0:
			if (!dialog_input_result[0])
				return;
			if (!conf_write(dialog_input_result))
				return;
			show_textbox(NULL, _("Can't create file!  Probably a nonexistent directory."), 5, 60);
			break;
		case 1:
			show_helptext(_("Save Alternate Configuration"), save_config_help);
			break;
		case KEY_ESC:
			return;
		}
	}
}

static void conf_cleanup(void)
{
	tcsetattr(1, TCSAFLUSH, &ios_org);
}

int main(int ac, char **av)
{
	struct symbol *sym;
	char *mode;
	int res;

	setlocale(LC_ALL, "");
	bindtextdomain(PACKAGE, LOCALEDIR);
	textdomain(PACKAGE);

	conf_parse(av[1] ? av[1] : "");
	conf_read(NULL);

	sym = sym_lookup("KERNELVERSION", 0);
	sym_calc_value(sym);
	sprintf(menu_backtitle, _(PROJECT_NAME" v%s Configuration"),
		sym_get_string_value(sym));

	mode = getenv("MENUCONFIG_MODE");
	if (mode) {
		if (!strcasecmp(mode, "single_menu"))
			single_menu_mode = 1;
	}

	tcgetattr(1, &ios_org);
	atexit(conf_cleanup);
	init_wsize();
	reset_dialog();
	init_dialog(menu_backtitle);
	do {
		conf(&rootmenu);
		dialog_clear();
		res = dialog_yesno(NULL,
				   _("Do you wish to save your "
				     "new "PROJECT_NAME" configuration?\n"
				     "<ESC><ESC> to continue."),
				   6, 60);
	} while (res == KEY_ESC);
	end_dialog();
	if (res == 0) {
		if (conf_write(NULL)) {
			fprintf(stderr, _("\n\n"
				"Error writing "PROJECT_NAME" configuration.\n"
				"Your configuration changes were NOT saved."
				"\n\n"));
			return 1;
		}
		printf(_("\n\n"
			"*** End of "PROJECT_NAME" configuration.\n"
			"*** Execute 'make' to build, or try 'make help'."
			"\n\n"));
	} else {
		fprintf(stderr, _("\n\n"
			"Your configuration changes were NOT saved."
			"\n\n"));
	}

	return 0;
}
