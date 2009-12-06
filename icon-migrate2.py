#!/usr/bin/env python
#
#       icon-migrate.py
#       
#       Copyright 2009 PCMan <pcman.tw@gmail.com>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import xml.dom.minidom, os, sys, os.path, shutil
from ConfigParser import *
import filecmp
import pygtk
import gtk

icon_theme_dir = ''
size_dirs = []
contexts = []

all_mappings=[]

subdirs = None

exts = ['.png', '.svg', '.xpm']

class Mapping:
    def __init__(self, xml_icon_node):
        self.new_name = xml_icon_node.getAttribute('name')
        self.old_names = []
        links = xml_icon_node.getElementsByTagName('link')
        for link in links:
            self.old_names.append(link.childNodes[0].data)

class Context:
    def __init__(self, xml_context_node):
        self.name = xml_context_node.getAttribute('dir')
        self.mappings = []
        icon_nodes = xml_context_node.getElementsByTagName('icon')
        for icon_node in icon_nodes:
            mapping = Mapping(icon_node)
            self.mappings.append(mapping)


def find_icon_file_in_context_dir(context_dir, icon_name):
    prefix = os.path.join(context_dir, icon_name)
    for ext in exts:
        file = prefix + ext
        if os.path.exists(file):
            return file
    return None

def find_icon_file_in_all_contexts(icon_name):
    for size_dir in size_dirs:
        sub_dirs = os.listdir(size_dir)
        for sub_dir in sub_dirs:
            if sub_dir[0] == '.':
                continue
            full_dir_name = os.path.join(size_dir, sub_dir)
            ret = find_icon_file_in_context_dir(full_dir_name, icon_name)
            if ret:
                return ret
    return None

def replace_link_with_real_file(file):
    real_path = os.path.realpath(file)
    os.unlink(file)
    shutil.copy2(real_path, file)
    print 'convert link to real file => copy %s to %s' % (real_path, file)


def convert_links_to_copies():
    for size in sizes:
        dirs = sizes[size]
        for dir in dirs: # dirs of different contexts
            dir = os.path.join(icon_theme_dir, dir)
            files = os.listdir(dir)
            for file in files:
                for ext in exts:
                    if file.endswith(ext): # it's an image file
                        if os.path.islink(file):
                            replace_link_with_real_file(file)
                        break

def is_icon_new_name(icon_name):
    for context in contexts:
        for mapping in context.mappings:
            if mapping.new_name == icon_name:
                return True
    return False

def convert_duplicated_files_to_symlinks():
    # find duplicated files with fdupes
    os.system( 'fdupes --nohidden -r nuoveXT2 > dups.txt' )
    files = []
    links = []

    print '\n\n--- svn commands ---\n'

    f = open( 'dups.txt', 'r' )
    for line in f:
        file = line.rstrip()
        if file != '':
            files.append(file)
        else:
            if len(files) == 0:
                continue

            files.sort( lambda x, y:len(x)-len(y) )

            primary = ''
            for file in files:
                # if the file has a valid new name,
                # symlink other duplicates to it
                basename = os.path.basename(file)
                (icon_name, ext) = os.path.splitext(basename)
                # print 'is_icon_new_name %s' % icon_name
                if is_icon_new_name(icon_name):
                    primary = file
                    break
            if primary == '':
                primary = files[0]
            print 'svn --force add %s' % primary

            for file in files:
                if file != primary:
                    # os.path.unlink(file)

                    print 'svn --force rm %s' % file
                    dir = os.path.dirname(file)
                    rel_path = os.path.relpath(primary, dir)
                    # os.path.symlink(rel_path, file)

                    links.append( (rel_path, file) )
                    # print 'need to symlink(%s %s)' % (rel_path, file)

            files = []

    print '---------- symlinks ------------'
    for link in links:
        print '$(LN_S) -f %s $(DESTDIR)$(datadir)/icons/%s' % (link[0], link[1])


def find_icon_file_in_dir(dir, icon_name):
    for ext in exts: # try .png, .svg, and .xpm
        base_name = icon_name + ext
        fpath=os.path.join(dir, base_name)
        if os.path.exists(fpath):
            return fpath, ext
    return None, None

symlinks=[]
files_to_del=[]

sizes = {}

def choose_icon(new_name, icons):
    dlg=gtk.Dialog()
    dlg.vbox.add(gtk.Label('Choose an icon for %s' % new_name))
    idx = 0
    for icon in icons:
        btn = gtk.Button(icon[0])
        btn.set_image(gtk.image_new_from_file(icon[0]))
        btn.connect('clicked', lambda btn, dlg, idx: dlg.response(idx), dlg, idx)
        idx = idx + 1
        dlg.vbox.add(btn)
    dlg.show_all()
    ret = dlg.run()
    dlg.destroy()
    return ret if ret >= 0 else -1

def find_icon_file_of_size(size, icon_name):
    subdirs=sizes[size]
    for sizedir in subdirs:
        dir = os.path.join(icon_theme_dir, sizedir)
        filename, ext = find_icon_file_in_dir(dir, icon_name)
        if filename:
            return filename, ext
    return None, None

def fix_icons_of_specified_size(size, subdir, mappings):
    print 'fix icons in %s of size %d' % (subdir, size)
    for mapping in mappings:
        print 'new_name: %s, %s', (subdir, mapping.new_name)
        dir = os.path.join(icon_theme_dir, subdir)
        (fpath, ext) = find_icon_file_in_dir(dir, mapping.new_name)
        if not fpath: # icon with new_name is not found, choose one icon from old_names
            choices=[]
            for old_name in mapping.old_names:
                for subdir2 in sizes[size]:
                    dir = os.path.join(icon_theme_dir, subdir2)
                    (fpath2, ext2) = find_icon_file_in_dir(dir, old_name)
                    if fpath2:
                        choices.append((fpath2, ext2))
            if not choices:
                print '%s is missing, need a new icon for it' % mapping.new_name
            elif len(choices) == 1:
                (fpath2, ext2) = choices[0]
                fpath = os.path.join(icon_theme_dir, subdir, (mapping.new_name + ext2))
                # copy old file name to new one
                shutil.copy2(fpath2, fpath)
                # print 'ls -s %s to %s' % (fpath, fpath2) # auto-choice
                # rel = os.path.relpath(fpath, os.path.dirname(fpath2))
                # symlinks.append((rel, fpath2))
            else:
                same = True
                for i in range(len(choices) - 1):
                    # different file extensions
                    if choices[i][1] != choices[i+1][1]:
                        same = False
                        break
                    # different file content
                    if not filecmp.cmp(choices[i][0], choices[i+1][0], False):
                        same = False
                        break
                if same: # they are actually the same image, can auto-choose
                    (fpath2, ext2) = choices[0]
                    fpath = os.path.join(icon_theme_dir, subdir, (mapping.new_name + ext2))
                    # copy old file name to new one
                    shutil.copy2(fpath2, fpath)
                    # print 'same img, symlink %s to %s' % (fpath, fpath2) # auto-choice
                    # rel = os.path.relpath(fpath, os.path.dirname(fpath2))
                    # symlinks.append((rel, fpath2))
                else:
                    print 'choices:', choices
                    ret = choose_icon(mapping.new_name, choices)
                    if ret >=0:
                        fpath = os.path.join(icon_theme_dir, subdir, (mapping.new_name + choices[ret][1]))
                        shutil.copy2(choices[ret][0], fpath)
                    else:
                        print '%s is missing, need a new icon for it' % mapping.new_name
        else:
            print '%s is found: %s' % (mapping.new_name, fpath)
            # create symlinks for old_names if they don't exist
            for old_name in mapping.old_names:
                # print 'find oldname:', old_name
                (fpath2, ext2) = find_icon_file_of_size(size, old_name)
                if not fpath2:
                    fpath2 = os.path.join(os.path.dirname(fpath), old_name + ext)
                    print 'copy newname to oldname: %s => %s' % (fpath, fpath2)
                    shutil.copy2(fpath, fpath2)

# ----------------------------------------------------------------
# start

if len(sys.argv) < 2:
    sys.exit()

icon_theme_dir = sys.argv[1]
cfg = SafeConfigParser()
cfg.read(os.path.join(icon_theme_dir, 'index.theme'))
subdirs = cfg.get('Icon Theme', 'Directories').split(',')

for subdir in subdirs:
    size=cfg.getint(subdir, 'Size')
    if size in sizes:
        sizes[size].append(subdir)
    else:
        l=[]
        l.append(subdir)
        sizes[size] = l

sizes.keys().sort()

# load the mappings
doc = xml.dom.minidom.parse('legacy-icon-mapping.xml')
context_nodes = doc.getElementsByTagName('context')
for context_node in context_nodes:
    context = Context(context_node)
    contexts.append(context)

# create a flat list of all available mappings
for ctx in contexts:
    for mapping in ctx.mappings:
        all_mappings.append(mapping)

# convert symlinks to real files
convert_links_to_copies()
# now, there is no symlink under the icon theme dir

for size in sizes:
    print 'for size: %d' % size
    # all sub dirs containing icons of specified size
    subdirs = sizes[size]

    for ctx in contexts:
        sub = None
        # find subdir corresponding speficied context
        for subdir in subdirs:
            ctx_dirname = os.path.basename(subdir)
            if ctx_dirname == ctx.name:
                sub = subdir
                print 'sub: %s' % sub
                break
        if not sub:
            sub = ctx.name
            print 'missing context: %s' % sub

        fix_icons_of_specified_size(size, sub, ctx.mappings)


print '\n\n--------------------symlinks----------------------\n\n'

convert_duplicated_files_to_symlinks()
